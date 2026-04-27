from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.core.domain_config import load_domain_config
from app.services.suggestion.segment_encoder import SegmentEncoderConfig, SegmentEncodingError, encode_segment

# The canonical 7 shape primitives (vocabulary v2, April 2026).
SHAPE_LABELS: tuple[str, ...] = (
    "plateau", "trend", "step", "spike", "cycle", "transient", "noise"
)


class PrototypeClassifierError(RuntimeError):
    """Raised when prototype classification cannot be completed safely."""


@dataclass(frozen=True)
class PrototypeClassifierConfig:
    temperature: float = 0.2
    missing_label_similarity: float = -1.0


@dataclass(frozen=True)
class LabeledSupportSegment:
    label: str
    values: tuple[tuple[float, ...], ...] | tuple[float, ...] | list[list[float]] | list[float]


@dataclass(frozen=True)
class PrototypeClassification:
    label: str
    confidence: float
    probabilities: dict[str, float]
    embedding: tuple[float, ...]


@dataclass(frozen=True)
class PrototypeMemoryConfig:
    min_update_confidence: float = 0.75
    max_buffer_per_label: int = 8
    max_prototype_drift: float = 0.45


@dataclass(frozen=True)
class PrototypeUpdateResult:
    applied: bool
    label: str
    reason: str
    confidence: float
    drift: float | None
    buffer_size: int


@dataclass(frozen=True)
class PrototypeMemoryBank:
    active_labels: tuple[str, ...]
    config: PrototypeMemoryConfig = PrototypeMemoryConfig()
    embeddings_by_label: dict[str, tuple[tuple[float, ...], ...]] = field(default_factory=dict)

    def build_prototypes(self) -> dict[str, np.ndarray]:
        prototypes: dict[str, np.ndarray] = {}
        for label in self.active_labels:
            embeddings = self.embeddings_by_label.get(label, ())
            if not embeddings:
                continue
            stacked = np.stack([np.asarray(embedding, dtype=np.float64) for embedding in embeddings], axis=0)
            prototypes[label] = _normalize(np.mean(stacked, axis=0))
        return prototypes

    def update(
        self,
        *,
        label: str,
        embedding: np.ndarray,
        confidence: float,
    ) -> tuple["PrototypeMemoryBank", PrototypeUpdateResult]:
        if label not in self.active_labels:
            raise PrototypeClassifierError(f"Prototype memory does not support label '{label}'.")
        if self.config.max_buffer_per_label < 1:
            raise PrototypeClassifierError("Prototype memory buffer size must be at least 1.")
        if confidence < self.config.min_update_confidence:
            return (
                self,
                PrototypeUpdateResult(
                    applied=False,
                    label=label,
                    reason="confidence_below_threshold",
                    confidence=float(confidence),
                    drift=None,
                    buffer_size=len(self.embeddings_by_label.get(label, ())),
                ),
            )

        normalized_embedding = tuple(float(value) for value in _normalize(np.asarray(embedding, dtype=np.float64)))
        current_embeddings = list(self.embeddings_by_label.get(label, ()))
        previous_prototype = self.build_prototypes().get(label)
        candidate_embeddings = tuple((current_embeddings + [normalized_embedding])[-self.config.max_buffer_per_label :])
        candidate_prototype = _build_prototype_from_embeddings(candidate_embeddings)
        drift = None if previous_prototype is None else float(np.linalg.norm(candidate_prototype - previous_prototype))
        if drift is not None and drift > self.config.max_prototype_drift:
            return (
                self,
                PrototypeUpdateResult(
                    applied=False,
                    label=label,
                    reason="drift_threshold_exceeded",
                    confidence=float(confidence),
                    drift=drift,
                    buffer_size=len(current_embeddings),
                ),
            )

        next_embeddings = dict(self.embeddings_by_label)
        next_embeddings[label] = candidate_embeddings
        return (
            PrototypeMemoryBank(
                active_labels=self.active_labels,
                config=self.config,
                embeddings_by_label=next_embeddings,
            ),
            PrototypeUpdateResult(
                applied=True,
                label=label,
                reason="updated",
                confidence=float(confidence),
                drift=drift,
                buffer_size=len(candidate_embeddings),
            ),
        )


class PrototypeChunkClassifier:
    def __init__(
        self,
        *,
        active_labels: tuple[str, ...] | None = None,
        encoder_config: SegmentEncoderConfig | None = None,
        classifier_config: PrototypeClassifierConfig | None = None,
    ):
        self._active_labels = active_labels or load_domain_config().active_chunk_types
        self._encoder_config = encoder_config or SegmentEncoderConfig()
        self._classifier_config = classifier_config or PrototypeClassifierConfig()

    @property
    def active_labels(self) -> tuple[str, ...]:
        return self._active_labels

    def build_prototypes(
        self,
        support_segments: list[LabeledSupportSegment] | tuple[LabeledSupportSegment, ...],
    ) -> dict[str, np.ndarray]:
        return self.build_memory_bank(support_segments).build_prototypes()

    def build_memory_bank(
        self,
        support_segments: list[LabeledSupportSegment] | tuple[LabeledSupportSegment, ...],
        *,
        memory_config: PrototypeMemoryConfig | None = None,
    ) -> PrototypeMemoryBank:
        if not support_segments:
            raise PrototypeClassifierError("Prototype classifier requires at least one support segment.")

        grouped: dict[str, list[tuple[float, ...]]] = {label: [] for label in self._active_labels}
        for support_segment in support_segments:
            if support_segment.label not in grouped:
                raise PrototypeClassifierError(
                    f"Support segment label '{support_segment.label}' is not active in the domain config."
                )
            try:
                embedding = encode_segment(support_segment.values, self._encoder_config).as_array()
            except SegmentEncodingError as exc:
                raise PrototypeClassifierError(str(exc)) from exc
            grouped[support_segment.label].append(tuple(float(value) for value in embedding))

        config = memory_config or PrototypeMemoryConfig()
        capped_grouped = {
            label: tuple(embeddings[-config.max_buffer_per_label :])
            for label, embeddings in grouped.items()
            if embeddings
        }
        return PrototypeMemoryBank(
            active_labels=self._active_labels,
            config=config,
            embeddings_by_label=capped_grouped,
        )

    def update_memory_bank(
        self,
        memory_bank: PrototypeMemoryBank,
        *,
        label: str,
        values: tuple[tuple[float, ...], ...] | tuple[float, ...] | list[list[float]] | list[float],
        confidence: float,
    ) -> tuple[PrototypeMemoryBank, PrototypeUpdateResult]:
        if memory_bank.active_labels != self._active_labels:
            raise PrototypeClassifierError("Prototype memory bank does not match classifier active labels.")
        try:
            embedding = encode_segment(values, self._encoder_config).as_array()
        except SegmentEncodingError as exc:
            raise PrototypeClassifierError(str(exc)) from exc
        return memory_bank.update(label=label, embedding=embedding, confidence=confidence)

    def classify_segment(
        self,
        values: tuple[tuple[float, ...], ...] | tuple[float, ...] | list[list[float]] | list[float],
        *,
        prototypes: dict[str, np.ndarray],
    ) -> PrototypeClassification:
        if self._classifier_config.temperature <= 0:
            raise PrototypeClassifierError("Prototype classifier temperature must be greater than 0.")

        try:
            embedding = encode_segment(values, self._encoder_config).as_array()
        except SegmentEncodingError as exc:
            raise PrototypeClassifierError(str(exc)) from exc

        similarities: dict[str, float] = {}
        for label in self._active_labels:
            prototype = prototypes.get(label)
            if prototype is None:
                similarities[label] = self._classifier_config.missing_label_similarity
                continue
            similarities[label] = float(np.dot(embedding, prototype))

        probabilities = _softmax_probabilities(similarities, self._classifier_config.temperature)
        predicted_label = max(probabilities, key=probabilities.get)
        return PrototypeClassification(
            label=predicted_label,
            confidence=probabilities[predicted_label],
            probabilities=probabilities,
            embedding=tuple(float(value) for value in embedding),
        )


def build_default_support_segments(
    active_labels: tuple[str, ...] | None = None,
    *,
    length: int = 24,
) -> list[LabeledSupportSegment]:
    if length < 8:
        raise PrototypeClassifierError("Default support segments require a minimum length of 8.")

    labels = active_labels or load_domain_config().active_chunk_types
    mid = length // 2
    quarter = max(2, length // 4)

    templates = {
        "trend": [index / max(1, length - 1) for index in range(length)],
        "plateau": [0.25] * length,
        "spike": ([0.0] * (mid - 1)) + [3.0] + ([0.0] * (length - mid)),
        "event": ([0.0] * quarter) + ([1.0] * (length - (quarter * 2))) + ([0.0] * quarter),
        "transition": ([0.0] * quarter)
        + [index / max(1, (length - (quarter * 2)) - 1) for index in range(length - (quarter * 2))]
        + ([1.0] * quarter),
        "periodic": [float(np.sin(index * (2 * np.pi / 6))) for index in range(length)],
    }

    support_segments: list[LabeledSupportSegment] = []
    for label in labels:
        if label not in templates:
            raise PrototypeClassifierError(f"No default support template is available for label '{label}'.")
        support_segments.append(
            LabeledSupportSegment(
                label=label,
                values=templates[label],
            )
        )
    return support_segments


def _build_prototype_from_embeddings(embeddings: tuple[tuple[float, ...], ...]) -> np.ndarray:
    stacked = np.stack([np.asarray(embedding, dtype=np.float64) for embedding in embeddings], axis=0)
    return _normalize(np.mean(stacked, axis=0))


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-8:
        raise PrototypeClassifierError("Prototype classifier received a near-zero prototype vector.")
    return vector / norm


def _softmax_probabilities(similarities: dict[str, float], temperature: float) -> dict[str, float]:
    labels = list(similarities)
    logits = np.asarray([similarities[label] / temperature for label in labels], dtype=np.float64)
    stabilized = logits - float(np.max(logits))
    weights = np.exp(stabilized)
    denominator = float(np.sum(weights))
    if denominator <= 0:
        raise PrototypeClassifierError("Prototype classifier could not normalize similarity scores.")
    probabilities = weights / denominator
    return {label: float(probability) for label, probability in zip(labels, probabilities, strict=True)}


# ---------------------------------------------------------------------------
# SEG-011: PrototypeShapeClassifier — few-shot, real corrections only
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SupportSegment:
    """A user-corrected labeled segment used as training support for SEG-011.

    Only segments with provenance='user' are accepted by PrototypeShapeClassifier.
    Synthetic support is rejected to prevent circular training (see SEG-002
    retrospective: pseudo-label-trained TCN learned nothing beyond the heuristic
    encoder because training targets were derived from the same heuristic).

    Attributes:
        shape_label: One of the 7 shape primitives (SHAPE_LABELS).
        values:      Raw segment signal (1-D), immutable tuple.
        provenance:  Must be 'user' for training; any other value is rejected.
    """

    shape_label: str
    values: tuple[float, ...]
    provenance: str = "user"


class PrototypeShapeClassifier:
    """Prototype-based few-shot shape classifier over the 7 shape primitives.

    Classifies segments by cosine similarity to per-class prototype vectors
    computed as the L2-normalised mean of support segment embeddings.
    The encoder (TCN from SEG-002, or heuristic fallback) remains frozen during
    online use — no gradient updates propagate through the encoder.

    Source:
        Snell et al. (2017) "Prototypical Networks for Few-shot Learning",
        NeurIPS 2017, arXiv:1703.05175.
        Eq. (1): μ_c = (1/|S_c|) Σ_{x∈S_c} f_φ(x)  [prototype computation]
        Eq. (2): p_φ(y=k|x) ∝ exp(−d(z, μ_k))        [cosine classification]
    """

    SHAPE_LABELS: tuple[str, ...] = SHAPE_LABELS

    def __init__(
        self,
        *,
        encoder_config: SegmentEncoderConfig | None = None,
        temperature: float = 0.1,
    ) -> None:
        self._encoder_config = encoder_config or SegmentEncoderConfig()
        self._temperature = temperature
        self._prototypes: dict[str, np.ndarray] = {}
        self._previous_prototypes: dict[str, np.ndarray] = {}

    @property
    def prototypes(self) -> dict[str, np.ndarray]:
        """Read-only view of the currently fitted prototype vectors."""
        return dict(self._prototypes)

    def fit_prototypes(
        self,
        support_segments: list[SupportSegment] | tuple[SupportSegment, ...],
    ) -> None:
        """Compute L2-normalised class prototypes from labeled support segments.

        Idempotent: calling twice with identical support produces identical prototypes.
        Rejects any segment with provenance != 'user' — synthetic segments cause
        circular training (see SEG-002 retrospective in train_prototype_classifier.py).

        Source: Snell et al. (2017) Eq. (1): μ_c = mean(L2_norm(f_φ(x)) for x in S_c).
        """
        for seg in support_segments:
            if seg.provenance != "user":
                raise PrototypeClassifierError(
                    f"PrototypeShapeClassifier requires provenance='user'; "
                    f"received '{seg.provenance}' for label '{seg.shape_label}'. "
                    f"Synthetic prototypes are rejected to prevent circular training "
                    f"(SEG-002 retrospective)."
                )
            if seg.shape_label not in self.SHAPE_LABELS:
                raise PrototypeClassifierError(
                    f"Unknown shape label '{seg.shape_label}'. "
                    f"Valid labels: {self.SHAPE_LABELS}."
                )

        by_class: dict[str, list[np.ndarray]] = {}
        for seg in support_segments:
            try:
                raw_emb = encode_segment(seg.values, self._encoder_config).as_array()
            except SegmentEncodingError as exc:
                raise PrototypeClassifierError(str(exc)) from exc
            normalized = _normalize(raw_emb)
            by_class.setdefault(seg.shape_label, []).append(normalized)

        self._previous_prototypes = {k: v.copy() for k, v in self._prototypes.items()}

        new_prototypes: dict[str, np.ndarray] = {}
        for y, embeddings in by_class.items():
            stacked = np.stack(embeddings, axis=0)
            mean_emb = np.mean(stacked, axis=0)
            new_prototypes[y] = _normalize(mean_emb)

        self._prototypes = new_prototypes

    def predict(
        self,
        X_seg: list[float] | tuple[float, ...] | np.ndarray,
    ) -> object:
        """Classify a segment's shape by cosine similarity to fitted prototypes.

        Returns a ShapeLabel (imported lazily to avoid circular imports).

        Source: Snell et al. (2017) Eq. (2): logit_k = dot(z, μ_k) / τ,
        p(y=k|x) = softmax(logits)[k].
        """
        if not self._prototypes:
            raise PrototypeClassifierError(
                "PrototypeShapeClassifier has no fitted prototypes; "
                "call fit_prototypes() first."
            )
        if self._temperature <= 0:
            raise PrototypeClassifierError("Temperature must be > 0.")

        try:
            raw_emb = encode_segment(X_seg, self._encoder_config).as_array()
        except SegmentEncodingError as exc:
            raise PrototypeClassifierError(str(exc)) from exc
        z = _normalize(raw_emb)

        logits: dict[str, float] = {
            y: float(np.dot(z, mu)) / self._temperature
            for y, mu in self._prototypes.items()
        }
        probabilities = _softmax_probabilities(logits, temperature=1.0)
        label = max(logits, key=logits.__getitem__)

        from app.services.suggestion.rule_classifier import ShapeLabel, uncertainty_margin  # noqa: PLC0415

        return ShapeLabel(
            label=label,
            confidence=probabilities[label],
            per_class_scores=logits,
            uncertain=uncertainty_margin(probabilities),
        )

    def get_prototype_drift(self, y: str) -> float:
        """Return ‖μ_y^new − μ_y^old‖₂ since the last fit_prototypes call.

        Returns 0.0 when y had no prototype before the most recent update.
        Raises PrototypeClassifierError when y has no current prototype.
        """
        new_proto = self._prototypes.get(y)
        if new_proto is None:
            raise PrototypeClassifierError(
                f"No fitted prototype for label '{y}'. "
                f"Fitted labels: {sorted(self._prototypes)}."
            )
        old_proto = self._previous_prototypes.get(y)
        if old_proto is None:
            return 0.0
        return float(np.linalg.norm(new_proto - old_proto))
