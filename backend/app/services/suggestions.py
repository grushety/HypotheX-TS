from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from dataclasses import dataclass
from typing import Any

from app.core.domain_config import load_domain_config
from app.schemas.suggestions import SuggestionProposal
from app.services.suggestion.duration_smoother import DurationRuleSmoother
from app.services.suggestion.boundary_proposal import (
    BoundaryProposalError,
    BoundaryCandidate,
    BoundaryProposal,
    BoundaryProposerConfig,
    ProvisionalSegment,
)
from app.services.suggestion.boundary_proposer import (
    BoundaryProposer,
    BoundaryProposerConfig as _NewBoundaryProposerConfig,
)
from app.services.suggestion.prototype_classifier import (
    LabeledSupportSegment,
    PrototypeChunkClassifier,
    PrototypeClassifierConfig,
    PrototypeClassifierError,
    PrototypeMemoryBank,
    PrototypeShapeClassifier,
    SupportSegment,
    build_default_support_segments,
)
from app.services.suggestion.segment_encoder import (
    SegmentEncoderConfig,
    SegmentEncodingError,
    encode_segment,
    slice_series,
)


class SuggestionServiceError(RuntimeError):
    """Raised when suggestion generation cannot be completed safely."""


# Mapping from the 7-shape primitive vocabulary (rule_classifier / SEG-011) to domain labels.
_PRIMITIVE_TO_DOMAIN: dict[str, str] = {
    "plateau":   "plateau",
    "trend":     "trend",
    "step":      "transition",
    "spike":     "spike",
    "cycle":     "periodic",
    "transient": "event",
    "noise":     "plateau",
}

# Reverse: domain labels → shape labels (for SEG-011 prototype threshold check).
_DOMAIN_TO_SHAPE: dict[str, str] = {
    "plateau":    "plateau",
    "trend":      "trend",
    "spike":      "spike",
    "event":      "transient",
    "transition": "step",
    "periodic":   "cycle",
}

# SEG-011 activation threshold: ≥ 5 corrections per class in ≥ 4 of 7 shape classes.
_PROTO_MIN_CORRECTIONS: int = 5
_PROTO_MIN_CLASSES: int = 4


@dataclass(frozen=True)
class AdaptResult:
    """Result of a few-shot prototype update (adapt_model).

    Attributes:
        model_version_id:   Version string in the format
                            ``suggestion-model-v1+adapt-{n}`` where *n* is the
                            cumulative update count for the session.
        prototypes_updated: Labels whose prototype was successfully updated
                            (i.e. confidence-gated and drift-guarded updates
                            that were applied).
        drift_report:       Per-label Euclidean drift of the prototype vector
                            after the update.  0.0 for the first update (no
                            previous prototype to compare against).
    """

    model_version_id: str
    prototypes_updated: tuple[str, ...]
    drift_report: dict[str, float]


@dataclass(frozen=True)
class DurationSmoothingConfig:
    default_min_length: int
    per_label_min_lengths: dict[str, int]

    def get_min_length(self, label: str | None) -> int:
        if not label:
            return self.default_min_length
        return self.per_label_min_lengths.get(label, self.default_min_length)


@dataclass(frozen=True)
class DurationSmoothingResult:
    segments: tuple[ProvisionalSegment, ...]
    merged_segment_ids: tuple[str, ...]


class BoundarySuggestionService:
    def __init__(
        self,
        *,
        proposer_name: str = "conservative-change-point-v1",
        model_version: str = "suggestion-model-v1",
        proposer_config: BoundaryProposerConfig | Mapping[str, Any] | None = None,
        encoder_config: SegmentEncoderConfig | Mapping[str, Any] | None = None,
        classifier_config: PrototypeClassifierConfig | Mapping[str, Any] | None = None,
        smoothing_config: DurationSmoothingConfig | None = None,
        boundary_method: str = "pelt",
    ):
        self._proposer_name = proposer_name
        self._model_version = model_version
        self._proposer_config = (
            proposer_config
            if isinstance(proposer_config, BoundaryProposerConfig)
            else BoundaryProposerConfig.from_mapping(dict(proposer_config) if proposer_config is not None else None)
        )
        self._encoder_config = (
            encoder_config
            if isinstance(encoder_config, SegmentEncoderConfig)
            else SegmentEncoderConfig(**dict(encoder_config)) if encoder_config is not None else SegmentEncoderConfig()
        )
        self._classifier_config = (
            classifier_config
            if isinstance(classifier_config, PrototypeClassifierConfig)
            else PrototypeClassifierConfig(**dict(classifier_config))
            if classifier_config is not None
            else PrototypeClassifierConfig()
        )
        self._classifier = PrototypeChunkClassifier(
            encoder_config=self._encoder_config,
            classifier_config=self._classifier_config,
        )
        self._shape_classifier = PrototypeShapeClassifier(encoder_config=self._encoder_config)
        self._smoothing_config = smoothing_config or build_duration_smoothing_config()
        self._duration_smoother = DurationRuleSmoother(
            L_min_per_class=dict(self._smoothing_config.per_label_min_lengths),
            default_min_length=self._smoothing_config.default_min_length,
        )
        self._boundary_method = boundary_method
        # In-memory prototype state per session: {session_id: (PrototypeMemoryBank, update_count)}
        self._sessions: dict[str, tuple[PrototypeMemoryBank, int]] = {}

    def propose(
        self,
        *,
        series_id: str,
        values: list[list[float]] | list[float],
        suggestion_id: str | None = None,
        proposer_config: Mapping[str, Any] | BoundaryProposerConfig | None = None,
        support_segments: list[LabeledSupportSegment] | tuple[LabeledSupportSegment, ...] | None = None,
        include_uncertainty: bool = False,
        use_llm_cold_start: bool = False,
        labeler: str = "prototype",
    ) -> SuggestionProposal:
        if not series_id:
            raise SuggestionServiceError("Suggestion proposal requires a non-empty series_id.")

        config = (
            proposer_config
            if isinstance(proposer_config, BoundaryProposerConfig)
            else BoundaryProposerConfig.from_mapping(dict(proposer_config) if proposer_config is not None else self._to_mapping())
        )

        try:
            proposal = self._run_boundary_proposer(values, config)
        except BoundaryProposalError as exc:
            raise SuggestionServiceError(str(exc)) from exc
        try:
            labeled_segments = self._classify_segments(
                values=values,
                proposal=proposal,
                support_segments=support_segments,
                use_llm_cold_start=use_llm_cold_start,
            )
        except (PrototypeClassifierError, SegmentEncodingError) as exc:
            raise SuggestionServiceError(str(exc)) from exc

        smoothed_segments = self._duration_smoother.smooth(labeled_segments)

        boundary_uncertainty = None
        segment_uncertainty = None
        if include_uncertainty:
            from app.services.suggestion.boundary_proposal import compute_boundary_scores  # noqa: PLC0415
            from app.services.suggestion.uncertainty import score_uncertainty  # noqa: PLC0415

            raw_scores = compute_boundary_scores(values, config)
            uncertainty = score_uncertainty(values, smoothed_segments, raw_scores)
            boundary_uncertainty = uncertainty.boundary_uncertainty
            segment_uncertainty = uncertainty.segment_uncertainty

        return SuggestionProposal(
            suggestionId=suggestion_id or f"suggestion-{series_id}",
            seriesId=series_id,
            modelVersion=self._model_version,
            seriesLength=proposal.seriesLength,
            channelCount=proposal.channelCount,
            candidateBoundaries=proposal.candidateBoundaries,
            provisionalSegments=smoothed_segments,
            proposerName=self._proposer_name,
            proposerConfig=config,
            boundary_uncertainty=boundary_uncertainty,
            segment_uncertainty=segment_uncertainty,
            labeler=labeler,
        )

    def adapt(
        self,
        *,
        session_id: str,
        support_segments: list[dict[str, object]],
    ) -> AdaptResult:
        """Apply few-shot prototype updates for a session from labeled support segments.

        The encoder weights stay frozen; only the in-memory ``PrototypeMemoryBank``
        for the session is mutated.  Confidence-gating and drift-guarding are
        enforced by ``PrototypeMemoryBank.update()`` (HTS-504).

        On first call for a ``session_id`` the bank is initialised from the
        default support templates (``build_default_support_segments``).

        Args:
            session_id:       Arbitrary caller-chosen session identifier.
            support_segments: Non-empty list of dicts; each must have ``label``
                              (str) and ``values`` (list); ``confidence``
                              (float ∈ [0, 1]) is optional, defaults to 1.0.

        Returns:
            AdaptResult with version string, applied label list, and drift report.

        Raises:
            SuggestionServiceError: If ``support_segments`` is empty, a label is
                                    unknown, or encoding fails.
        """
        if not support_segments:
            raise SuggestionServiceError("adapt() requires at least one support segment.")

        # Initialise session from default templates on first access.
        if session_id not in self._sessions:
            default_support = build_default_support_segments(self._classifier.active_labels)
            try:
                initial_bank = self._classifier.build_memory_bank(default_support)
            except PrototypeClassifierError as exc:
                raise SuggestionServiceError(str(exc)) from exc
            self._sessions[session_id] = (initial_bank, 0)

        memory_bank, update_count = self._sessions[session_id]

        prototypes_updated: list[str] = []
        drift_report: dict[str, float] = {}

        for raw_seg in support_segments:
            label = raw_seg.get("label")
            values = raw_seg.get("values")
            confidence = float(raw_seg.get("confidence", 1.0))

            if not isinstance(label, str) or not label:
                raise SuggestionServiceError("Each support segment must have a non-empty 'label'.")
            if values is None:
                raise SuggestionServiceError("Each support segment must have a 'values' field.")

            try:
                embedding = encode_segment(values, self._encoder_config).as_array()
            except SegmentEncodingError as exc:
                raise SuggestionServiceError(str(exc)) from exc

            try:
                new_bank, result = memory_bank.update(
                    label=label,
                    embedding=embedding,
                    confidence=confidence,
                )
            except PrototypeClassifierError as exc:
                raise SuggestionServiceError(str(exc)) from exc

            if result.applied:
                memory_bank = new_bank
                prototypes_updated.append(label)
                drift_report[label] = float(result.drift) if result.drift is not None else 0.0

            update_count += 1

        self._sessions[session_id] = (memory_bank, update_count)

        return AdaptResult(
            model_version_id=f"suggestion-model-v1+adapt-{update_count}",
            prototypes_updated=tuple(prototypes_updated),
            drift_report=drift_report,
        )

    def _run_boundary_proposer(
        self,
        values: list[list[float]] | list[float],
        config: BoundaryProposerConfig,
    ) -> BoundaryProposal:
        """Run BoundaryProposer and convert output to BoundaryProposal format."""
        arr = np.asarray(values, dtype=float)
        if arr.ndim == 1:
            channel_count = 1
            series_length = int(arr.shape[0])
        else:
            if arr.shape[0] > arr.shape[1]:
                arr = arr.T
            channel_count = int(arr.shape[0])
            series_length = int(arr.shape[1])

        if series_length < 2:
            raise BoundaryProposalError("Boundary proposer requires a series with at least 2 time steps.")

        proposer = BoundaryProposer(
            _NewBoundaryProposerConfig(
                method=self._boundary_method,  # type: ignore[arg-type]
                min_segment_length=config.min_segment_length,
                max_cps=config.max_boundaries,
            )
        )
        try:
            new_candidates = proposer.propose(values)
        except Exception as exc:
            raise BoundaryProposalError(str(exc)) from exc

        old_candidates = [
            BoundaryCandidate(
                boundaryIndex=bc.timestamp,
                score=round(bc.score, 6),
                confidence=round(min(1.0, max(0.0, bc.score)), 6),
            )
            for bc in new_candidates
        ]
        segments = self._build_provisional_segments(series_length, old_candidates)
        return BoundaryProposal(
            seriesLength=series_length,
            channelCount=channel_count,
            candidateBoundaries=tuple(old_candidates),
            provisionalSegments=tuple(segments),
            config=config,
        )

    @staticmethod
    def _build_provisional_segments(
        series_length: int,
        boundaries: list[BoundaryCandidate],
    ) -> list[ProvisionalSegment]:
        segments: list[ProvisionalSegment] = []
        start = 0
        for i, bc in enumerate(sorted(boundaries, key=lambda b: b.boundaryIndex), start=1):
            segments.append(
                ProvisionalSegment(
                    segmentId=f"segment-{i:03d}",
                    startIndex=start,
                    endIndex=bc.boundaryIndex - 1,
                )
            )
            start = bc.boundaryIndex
        segments.append(
            ProvisionalSegment(
                segmentId=f"segment-{len(segments) + 1:03d}",
                startIndex=start,
                endIndex=series_length - 1,
            )
        )
        return segments

    def _label_segments_with_llm(
        self,
        values: list[list[float]] | list[float],
        segments: tuple[ProvisionalSegment, ...],
    ) -> tuple[ProvisionalSegment, ...]:
        """Label provisional segments using the LLM cold-start labeler.

        Called only when ``use_llm_cold_start=True`` and no support segments were
        provided.  Falls back to ``"other"`` with confidence 0.0 if the model is
        unavailable (see ``LlmSegmentLabeler.label_segment``).
        """
        from app.services.suggestion.llm_labeler import LlmSegmentLabeler  # noqa: PLC0415

        labeler = LlmSegmentLabeler.get_instance()
        labeled: list[ProvisionalSegment] = []
        for seg in segments:
            seg_values = slice_series(values, seg.startIndex, seg.endIndex)
            result = labeler.label_segment(seg_values, self._classifier.active_labels)
            labeled.append(
                ProvisionalSegment(
                    segmentId=seg.segmentId,
                    startIndex=seg.startIndex,
                    endIndex=seg.endIndex,
                    provenance=seg.provenance,
                    label=result.label,
                    confidence=round(result.confidence, 6),
                    labelScores=None,
                )
            )
        return tuple(labeled)

    def _to_mapping(self) -> dict[str, object]:
        return {
            "window_size": self._proposer_config.window_size,
            "min_segment_length": self._proposer_config.min_segment_length,
            "score_threshold": self._proposer_config.score_threshold,
            "max_boundaries": self._proposer_config.max_boundaries,
        }

    def _label_segments_with_rule_classifier(
        self,
        values: list[list[float]] | list[float],
        segments: tuple[ProvisionalSegment, ...],
    ) -> tuple[ProvisionalSegment, ...]:
        """Label provisional segments using the deterministic rule-based classifier.

        Invoked when use_llm_cold_start=False and no support segments exist (cold start).
        Maps the 7-primitive shape vocabulary to domain active chunk types.
        """
        from app.services.suggestion.rule_classifier import RuleBasedShapeClassifier  # noqa: PLC0415

        active = set(self._classifier.active_labels)

        clf = RuleBasedShapeClassifier()
        series_1d = np.asarray(values, dtype=np.float64).ravel()
        labeled: list[ProvisionalSegment] = []
        for seg in segments:
            seg_values = slice_series(values, seg.startIndex, seg.endIndex).ravel()
            ctx_pre = series_1d[max(0, seg.startIndex - 10): seg.startIndex]
            ctx_post = series_1d[seg.endIndex + 1: seg.endIndex + 11]
            result = clf.classify_shape(seg_values, ctx_pre, ctx_post)
            raw_label = result.label
            domain_label = _PRIMITIVE_TO_DOMAIN.get(raw_label, raw_label)
            if domain_label not in active:
                domain_label = list(self._classifier.active_labels)[0]
            labeled.append(
                ProvisionalSegment(
                    segmentId=seg.segmentId,
                    startIndex=seg.startIndex,
                    endIndex=seg.endIndex,
                    provenance=seg.provenance,
                    label=domain_label,
                    confidence=round(result.confidence, 6),
                    labelScores=None,
                )
            )
        return tuple(labeled)

    def _classify_segments(
        self,
        *,
        values: list[list[float]] | list[float],
        proposal,
        support_segments: list[LabeledSupportSegment] | tuple[LabeledSupportSegment, ...] | None,
        use_llm_cold_start: bool = False,
    ) -> tuple[ProvisionalSegment, ...]:
        if not support_segments:
            if use_llm_cold_start:
                return self._label_segments_with_llm(values, proposal.provisionalSegments)
            return self._label_segments_with_rule_classifier(values, proposal.provisionalSegments)

        if _should_use_prototype_shape_classifier(support_segments):
            return self._label_segments_with_shape_classifier(
                values, proposal.provisionalSegments, support_segments
            )

        prototypes = self._classifier.build_prototypes(support_segments)
        labeled_segments = []
        for provisional_segment in proposal.provisionalSegments:
            segment_values = slice_series(values, provisional_segment.startIndex, provisional_segment.endIndex)
            classification = self._classifier.classify_segment(segment_values, prototypes=prototypes)
            labeled_segments.append(
                provisional_segment.__class__(
                    segmentId=provisional_segment.segmentId,
                    startIndex=provisional_segment.startIndex,
                    endIndex=provisional_segment.endIndex,
                    provenance=provisional_segment.provenance,
                    label=classification.label,
                    confidence=round(classification.confidence, 6),
                    labelScores=_rounded_probabilities(classification.probabilities),
                )
            )
        return tuple(labeled_segments)

    def _label_segments_with_shape_classifier(
        self,
        values: list[list[float]] | list[float],
        segments: tuple[ProvisionalSegment, ...],
        support_segments: list[LabeledSupportSegment] | tuple[LabeledSupportSegment, ...],
    ) -> tuple[ProvisionalSegment, ...]:
        """Label segments using SEG-011 PrototypeShapeClassifier.

        Activated when ≥ 5 user corrections per class exist in ≥ 4 of the 7 shape
        primitives.  Domain labels in support_segments are mapped to shape labels
        before fitting; shape predictions are mapped back to domain labels for the
        ProvisionalSegment contract.
        """
        shape_support: list[SupportSegment] = [
            SupportSegment(
                shape_label=_DOMAIN_TO_SHAPE.get(seg.label, seg.label),
                values=seg.values,
                provenance="user",
            )
            for seg in support_segments
        ]

        try:
            self._shape_classifier.fit_prototypes(shape_support)
        except PrototypeClassifierError as exc:
            raise SuggestionServiceError(str(exc)) from exc

        active = set(self._classifier.active_labels)
        labeled: list[ProvisionalSegment] = []
        for seg in segments:
            seg_values = slice_series(values, seg.startIndex, seg.endIndex)
            try:
                result = self._shape_classifier.predict(seg_values)
            except PrototypeClassifierError as exc:
                raise SuggestionServiceError(str(exc)) from exc

            domain_label = _PRIMITIVE_TO_DOMAIN.get(result.label, result.label)
            if domain_label not in active:
                domain_label = list(self._classifier.active_labels)[0]

            labeled.append(
                ProvisionalSegment(
                    segmentId=seg.segmentId,
                    startIndex=seg.startIndex,
                    endIndex=seg.endIndex,
                    provenance=seg.provenance,
                    label=domain_label,
                    confidence=round(result.confidence, 6),
                    labelScores=None,
                )
            )
        return tuple(labeled)


def _should_use_prototype_shape_classifier(
    support_segments: list[LabeledSupportSegment] | tuple[LabeledSupportSegment, ...],
) -> bool:
    """Return True when ≥ 5 corrections per class exist in ≥ 4 of the 7 shape primitives.

    Domain labels are mapped to shape labels before counting so that the threshold
    is expressed against the canonical 7-shape vocabulary used by SEG-011.
    """
    shape_counts: dict[str, int] = {}
    for seg in support_segments:
        shape = _DOMAIN_TO_SHAPE.get(seg.label, seg.label)
        shape_counts[shape] = shape_counts.get(shape, 0) + 1
    classes_above_threshold = sum(
        1 for count in shape_counts.values() if count >= _PROTO_MIN_CORRECTIONS
    )
    return classes_above_threshold >= _PROTO_MIN_CLASSES


def build_duration_smoothing_config() -> DurationSmoothingConfig:
    domain_config = load_domain_config()
    duration_limits = domain_config.duration_limits
    default_min_length = max(1, int(duration_limits.get("minimumSegmentLength", 1)))
    return DurationSmoothingConfig(
        default_min_length=default_min_length,
        per_label_min_lengths={
            "event": max(1, int(duration_limits.get("eventMinLength", default_min_length))),
            "transition": max(1, int(duration_limits.get("transitionMinLength", default_min_length))),
            "periodic": max(1, int(duration_limits.get("periodicMinLength", default_min_length))),
        },
    )


def smooth_provisional_segments(
    provisional_segments: tuple[ProvisionalSegment, ...] | list[ProvisionalSegment],
    *,
    config: DurationSmoothingConfig | None = None,
) -> DurationSmoothingResult:
    smoothing_config = config or build_duration_smoothing_config()
    if not provisional_segments:
        return DurationSmoothingResult(segments=tuple(), merged_segment_ids=tuple())

    segments = list(provisional_segments)
    merged_segment_ids: list[str] = []
    changed = True
    while changed and len(segments) > 1:
        changed = False
        for index, segment in enumerate(segments):
            if _segment_length(segment) >= smoothing_config.get_min_length(segment.label):
                continue
            merge_index = _select_merge_neighbor(segments, index)
            segments, merged_id = _merge_segment_pair(segments, index, merge_index)
            merged_segment_ids.append(merged_id)
            changed = True
            break

    renumbered_segments = tuple(
        ProvisionalSegment(
            segmentId=f"segment-{segment_number:03d}",
            startIndex=segment.startIndex,
            endIndex=segment.endIndex,
            provenance=segment.provenance,
            label=segment.label,
            confidence=segment.confidence,
            labelScores=segment.labelScores,
        )
        for segment_number, segment in enumerate(segments, start=1)
    )
    return DurationSmoothingResult(
        segments=renumbered_segments,
        merged_segment_ids=tuple(merged_segment_ids),
    )


def _segment_length(segment: ProvisionalSegment) -> int:
    return segment.endIndex - segment.startIndex + 1


def _select_merge_neighbor(segments: list[ProvisionalSegment], index: int) -> int:
    if index <= 0:
        return 1
    if index >= len(segments) - 1:
        return len(segments) - 2

    target = segments[index]
    left = segments[index - 1]
    right = segments[index + 1]
    left_score = _neighbor_compatibility_score(target, left)
    right_score = _neighbor_compatibility_score(target, right)
    if right_score > left_score:
        return index + 1
    if left_score > right_score:
        return index - 1
    if _segment_length(right) > _segment_length(left):
        return index + 1
    return index - 1


def _neighbor_compatibility_score(target: ProvisionalSegment, neighbor: ProvisionalSegment) -> float:
    score = 0.0
    if target.labelScores and neighbor.label:
        score += float(target.labelScores.get(neighbor.label, 0.0))
    if target.label and neighbor.label == target.label:
        score += 0.5
    if neighbor.confidence is not None:
        score += float(neighbor.confidence) * 0.05
    score += min(_segment_length(neighbor), 10) * 0.001
    return score


def _merge_segment_pair(
    segments: list[ProvisionalSegment],
    short_index: int,
    neighbor_index: int,
) -> tuple[list[ProvisionalSegment], str]:
    short_segment = segments[short_index]
    neighbor_segment = segments[neighbor_index]
    keep_left = neighbor_index < short_index
    merged_segment = ProvisionalSegment(
        segmentId=neighbor_segment.segmentId,
        startIndex=neighbor_segment.startIndex if keep_left else short_segment.startIndex,
        endIndex=short_segment.endIndex if keep_left else neighbor_segment.endIndex,
        provenance=neighbor_segment.provenance,
        label=neighbor_segment.label,
        confidence=_merge_confidence(neighbor_segment, short_segment),
        labelScores=_merge_label_scores(neighbor_segment, short_segment),
    )

    updated_segments: list[ProvisionalSegment] = []
    for index, segment in enumerate(segments):
        if index == short_index:
            continue
        if index == neighbor_index:
            updated_segments.append(merged_segment)
            continue
        updated_segments.append(segment)
    updated_segments.sort(key=lambda segment: segment.startIndex)
    return updated_segments, short_segment.segmentId


def _merge_confidence(primary: ProvisionalSegment, absorbed: ProvisionalSegment) -> float | None:
    if primary.confidence is None and absorbed.confidence is None:
        return None
    if primary.confidence is None:
        return absorbed.confidence
    if absorbed.confidence is None:
        return primary.confidence

    primary_length = _segment_length(primary)
    absorbed_length = _segment_length(absorbed)
    total_length = primary_length + absorbed_length
    return round(
        ((primary.confidence * primary_length) + (absorbed.confidence * absorbed_length)) / total_length,
        6,
    )


def _merge_label_scores(primary: ProvisionalSegment, absorbed: ProvisionalSegment) -> dict[str, float] | None:
    if primary.labelScores is None and absorbed.labelScores is None:
        return None
    if primary.labelScores is None:
        return dict(absorbed.labelScores or {})
    if absorbed.labelScores is None:
        return dict(primary.labelScores)

    primary_length = _segment_length(primary)
    absorbed_length = _segment_length(absorbed)
    total_length = primary_length + absorbed_length
    labels = set(primary.labelScores) | set(absorbed.labelScores)
    merged = {
        label: round(
            (
                (primary.labelScores.get(label, 0.0) * primary_length)
                + (absorbed.labelScores.get(label, 0.0) * absorbed_length)
            )
            / total_length,
            6,
        )
        for label in labels
    }
    return _rounded_probabilities(merged)


def _rounded_probabilities(probabilities: dict[str, float]) -> dict[str, float]:
    rounded = {label: round(probability, 6) for label, probability in probabilities.items()}
    total = round(sum(rounded.values()), 6)
    if total == 1.0:
        return rounded

    dominant_label = max(rounded, key=rounded.get)
    adjusted_value = round(rounded[dominant_label] + (1.0 - total), 6)
    rounded[dominant_label] = max(0.0, adjusted_value)
    return rounded
