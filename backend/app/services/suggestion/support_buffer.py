"""Support buffer for few-shot prototype adaptation (SEG-020).

Maintains a per-class bounded FIFO memory of user-corrected segments.
Every N accepted corrections, recomputes prototypes via PrototypeShapeClassifier
and tracks prototype drift to detect unstable adaptation.

Source:
    Snell, Swersky, Zemel (2017) "Prototypical Networks for Few-shot Learning",
    NeurIPS 2017, arXiv:1703.05175 (prototype update rule).
    Wang, Yao, Kwok, Ni (2020) "Generalizing from a Few Examples: A Survey on
    Few-Shot Learning", ACM Computing Surveys 53(3):63 (bounded-memory buffer
    strategies, §4.3 "Memory-Augmented Methods").

Online adaptation invariant (MVP):
    Encoder weights remain frozen during buffer updates. Only the prototype
    vectors are recomputed. Full encoder fine-tuning is a separate ticket.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass

import numpy as np

from app.services.suggestion.prototype_classifier import (
    PrototypeClassifierError,
    PrototypeShapeClassifier,
    SHAPE_LABELS,
    SupportSegment,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SupportBufferConfig:
    """Configuration for SupportBuffer.

    Attributes:
        cap_per_class:    Max segments retained per shape class (FIFO eviction).
        drift_threshold:  Log a warning when max drift exceeds this value.
        n_update:         Trigger prototype recompute every this many accepted
                          corrections.
        confidence_gate:  Minimum classifier confidence to accept a correction.
    """

    cap_per_class: int = 50
    drift_threshold: float = 0.3
    n_update: int = 5
    confidence_gate: float = 0.7


@dataclass(frozen=True)
class AcceptResult:
    """Outcome of a SupportBuffer.accept_correction() call.

    Attributes:
        accepted:           True when the correction was buffered.
        reason:             Short code explaining the decision:
                            'buffered'              — accepted and stored,
                            'below_confidence_gate' — confidence too low,
                            'unknown_label'         — label not in SHAPE_LABELS.
        prototypes_updated: True when a prototype recompute was triggered.
        drift:              max_y ‖μ_y^new − μ_y^old‖₂ over classes present in
                            both versions. None when no recompute occurred.
    """

    accepted: bool
    reason: str
    prototypes_updated: bool = False
    drift: float | None = None


class SupportBuffer:
    """Bounded per-class support buffer for few-shot prototype adaptation.

    Accumulates user-corrected segments per shape class (FIFO, capped at
    config.cap_per_class). Every config.n_update accepted corrections,
    calls PrototypeShapeClassifier.fit_prototypes() to recompute prototypes
    and computes the resulting prototype drift.

    Drift exceeding config.drift_threshold is logged as a WARNING so that
    UI-002 can surface the instability signal to the user.

    The previous prototype set (prev_prototypes) is retained after each
    recompute to allow the caller to offer a rollback.
    """

    def __init__(self, config: SupportBufferConfig | None = None) -> None:
        self.config = config or SupportBufferConfig()
        self.buffers: dict[str, deque[SupportSegment]] = {
            y: deque(maxlen=self.config.cap_per_class) for y in SHAPE_LABELS
        }
        self.total_accepted: int = 0
        self._prototypes: dict[str, np.ndarray] = {}
        self._prev_prototypes: dict[str, np.ndarray] = {}

    @property
    def prev_prototypes(self) -> dict[str, np.ndarray]:
        """Read-only view of prototypes before the most recent recompute."""
        return dict(self._prev_prototypes)

    def accept_correction(
        self,
        segment_X: list[float] | tuple[float, ...],
        label: str,
        confidence: float,
        classifier: PrototypeShapeClassifier,
    ) -> AcceptResult:
        """Buffer a user correction and optionally recompute prototypes.

        A correction is rejected (not buffered) when:
        - confidence < config.confidence_gate
        - label is not one of the 7 SHAPE_LABELS

        A prototype recompute is triggered when total_accepted % n_update == 0
        after incrementing. On recompute, drift is computed as
        max_y ‖μ_y^new − μ_y^old‖₂; if drift > config.drift_threshold a
        WARNING is logged.

        Args:
            segment_X:  Raw 1-D signal for the corrected segment.
            label:      Shape label assigned by the user.
            confidence: Classifier confidence at correction time (gating).
            classifier: PrototypeShapeClassifier to call fit_prototypes() on.

        Returns:
            AcceptResult with accepted, reason, prototypes_updated, and drift.
        """
        if confidence < self.config.confidence_gate:
            return AcceptResult(accepted=False, reason="below_confidence_gate")

        if label not in self.buffers:
            return AcceptResult(accepted=False, reason="unknown_label")

        seg = SupportSegment(
            shape_label=label,
            values=tuple(float(v) for v in segment_X),
            provenance="user",
        )
        self.buffers[label].append(seg)
        self.total_accepted += 1

        if self.total_accepted % self.config.n_update == 0:
            self._prev_prototypes = {k: v.copy() for k, v in self._prototypes.items()}
            all_support = self._flatten_buffers()
            try:
                classifier.fit_prototypes(all_support)
            except PrototypeClassifierError as exc:
                logger.error("Prototype recompute failed: %s", exc)
                return AcceptResult(accepted=True, reason="buffered", prototypes_updated=False)

            self._prototypes = classifier.prototypes
            drift = self._compute_max_drift()

            if drift > self.config.drift_threshold:
                logger.warning(
                    "Prototype drift %.4f exceeds threshold %.4f after %d accepted corrections.",
                    drift,
                    self.config.drift_threshold,
                    self.total_accepted,
                )

            return AcceptResult(
                accepted=True,
                reason="buffered",
                prototypes_updated=True,
                drift=drift,
            )

        return AcceptResult(accepted=True, reason="buffered")

    def _flatten_buffers(self) -> list[SupportSegment]:
        result: list[SupportSegment] = []
        for deq in self.buffers.values():
            result.extend(deq)
        return result

    def _compute_max_drift(self) -> float:
        """Return max_y ‖μ_y^new − μ_y^old‖₂ over classes in both prototype sets.

        Returns 0.0 on the first recompute (no previous prototypes exist).

        Source: Wang et al. (2020) §4.3 — drift as ℓ₂ distance between
        successive prototype vectors is the standard stability metric for
        few-shot memory modules.
        """
        if not self._prev_prototypes:
            return 0.0
        drifts = [
            float(np.linalg.norm(new_proto - self._prev_prototypes[y]))
            for y, new_proto in self._prototypes.items()
            if y in self._prev_prototypes
        ]
        return max(drifts) if drifts else 0.0

    def to_dict(self) -> dict:
        """Serialise buffer state to a JSON-compatible dict.

        Prototype vectors are NOT serialised — they are recomputed from the
        stored segments when needed. Only segments and total_accepted are
        persisted so that session state can be restored exactly.
        """
        return {
            "total_accepted": self.total_accepted,
            "config": {
                "cap_per_class": self.config.cap_per_class,
                "drift_threshold": self.config.drift_threshold,
                "n_update": self.config.n_update,
                "confidence_gate": self.config.confidence_gate,
            },
            "buffers": {
                label: [
                    {"shape_label": seg.shape_label, "values": list(seg.values)}
                    for seg in deq
                ]
                for label, deq in self.buffers.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SupportBuffer":
        """Deserialise buffer state from a JSON-compatible dict.

        After loading, call classifier.fit_prototypes(buffer._flatten_buffers())
        to restore the prototype vectors if needed.
        """
        config_data = data.get("config", {})
        config = SupportBufferConfig(
            cap_per_class=int(config_data.get("cap_per_class", 50)),
            drift_threshold=float(config_data.get("drift_threshold", 0.3)),
            n_update=int(config_data.get("n_update", 5)),
            confidence_gate=float(config_data.get("confidence_gate", 0.7)),
        )
        buf = cls(config=config)
        buf.total_accepted = int(data.get("total_accepted", 0))
        for label, segments in data.get("buffers", {}).items():
            if label in buf.buffers:
                for seg_data in segments:
                    buf.buffers[label].append(
                        SupportSegment(
                            shape_label=str(seg_data["shape_label"]),
                            values=tuple(float(v) for v in seg_data["values"]),
                            provenance="user",
                        )
                    )
        return buf
