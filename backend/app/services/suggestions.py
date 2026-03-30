from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.schemas.suggestions import SuggestionProposal
from app.services.suggestion.boundary_proposal import BoundaryProposalError, BoundaryProposerConfig, propose_boundaries
from app.services.suggestion.prototype_classifier import (
    LabeledSupportSegment,
    PrototypeChunkClassifier,
    PrototypeClassifierConfig,
    PrototypeClassifierError,
)
from app.services.suggestion.segment_encoder import SegmentEncoderConfig, SegmentEncodingError, slice_series


class SuggestionServiceError(RuntimeError):
    """Raised when suggestion generation cannot be completed safely."""


class BoundarySuggestionService:
    def __init__(
        self,
        *,
        proposer_name: str = "conservative-change-point-v1",
        model_version: str = "suggestion-model-v1",
        proposer_config: BoundaryProposerConfig | Mapping[str, Any] | None = None,
        encoder_config: SegmentEncoderConfig | Mapping[str, Any] | None = None,
        classifier_config: PrototypeClassifierConfig | Mapping[str, Any] | None = None,
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

        return SuggestionProposal(
            suggestionId=suggestion_id or f"suggestion-{series_id}",
            seriesId=series_id,
            modelVersion=self._model_version,
            seriesLength=proposal.seriesLength,
            channelCount=proposal.channelCount,
            candidateBoundaries=proposal.candidateBoundaries,
            provisionalSegments=labeled_segments,
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
    ):
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


def _rounded_probabilities(probabilities: dict[str, float]) -> dict[str, float]:
    rounded = {
        label: round(probability, 6)
        for label, probability in probabilities.items()
    }
    total = round(sum(rounded.values()), 6)
    if total == 1.0:
        return rounded

    dominant_label = max(rounded, key=rounded.get)
    adjusted_value = round(rounded[dominant_label] + (1.0 - total), 6)
    rounded[dominant_label] = max(0.0, adjusted_value)
    return rounded
