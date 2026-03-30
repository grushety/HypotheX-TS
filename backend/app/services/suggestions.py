from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.core.domain_config import load_domain_config
from app.schemas.suggestions import SuggestionProposal
from app.services.suggestion.boundary_proposal import (
    BoundaryProposalError,
    BoundaryProposerConfig,
    ProvisionalSegment,
    propose_boundaries,
)
from app.services.suggestion.prototype_classifier import (
    LabeledSupportSegment,
    PrototypeChunkClassifier,
    PrototypeClassifierConfig,
    PrototypeClassifierError,
)
from app.services.suggestion.segment_encoder import SegmentEncoderConfig, SegmentEncodingError, slice_series


class SuggestionServiceError(RuntimeError):
    """Raised when suggestion generation cannot be completed safely."""


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
        self._smoothing_config = smoothing_config or build_duration_smoothing_config()

    def propose(
        self,
        *,
        series_id: str,
        values: list[list[float]] | list[float],
        suggestion_id: str | None = None,
        proposer_config: Mapping[str, Any] | BoundaryProposerConfig | None = None,
        support_segments: list[LabeledSupportSegment] | tuple[LabeledSupportSegment, ...] | None = None,
    ) -> SuggestionProposal:
        if not series_id:
            raise SuggestionServiceError("Suggestion proposal requires a non-empty series_id.")

        config = (
            proposer_config
            if isinstance(proposer_config, BoundaryProposerConfig)
            else BoundaryProposerConfig.from_mapping(dict(proposer_config) if proposer_config is not None else self._to_mapping())
        )

        try:
            proposal = propose_boundaries(values, config)
        except BoundaryProposalError as exc:
            raise SuggestionServiceError(str(exc)) from exc
        try:
            labeled_segments = self._classify_segments(
                values=values,
                proposal=proposal,
                support_segments=support_segments,
            )
        except (PrototypeClassifierError, SegmentEncodingError) as exc:
            raise SuggestionServiceError(str(exc)) from exc

        smoothed_segments = smooth_provisional_segments(labeled_segments, config=self._smoothing_config).segments
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
        )

    def _to_mapping(self) -> dict[str, object]:
        return {
            "window_size": self._proposer_config.window_size,
            "min_segment_length": self._proposer_config.min_segment_length,
            "score_threshold": self._proposer_config.score_threshold,
            "max_boundaries": self._proposer_config.max_boundaries,
        }

    def _classify_segments(
        self,
        *,
        values: list[list[float]] | list[float],
        proposal,
        support_segments: list[LabeledSupportSegment] | tuple[LabeledSupportSegment, ...] | None,
    ) -> tuple[ProvisionalSegment, ...]:
        if not support_segments:
            return proposal.provisionalSegments

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
