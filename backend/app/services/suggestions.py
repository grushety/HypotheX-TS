from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.schemas.suggestions import SuggestionProposal
from app.services.suggestion.boundary_proposal import BoundaryProposalError, BoundaryProposerConfig, propose_boundaries


class SuggestionServiceError(RuntimeError):
    """Raised when suggestion generation cannot be completed safely."""


class BoundarySuggestionService:
    def __init__(
        self,
        *,
        proposer_name: str = "conservative-change-point-v1",
        model_version: str = "suggestion-model-v1",
        proposer_config: BoundaryProposerConfig | Mapping[str, Any] | None = None,
    ):
        self._proposer_name = proposer_name
        self._model_version = model_version
        self._proposer_config = (
            proposer_config
            if isinstance(proposer_config, BoundaryProposerConfig)
            else BoundaryProposerConfig.from_mapping(dict(proposer_config) if proposer_config is not None else None)
        )

    def propose(
        self,
        *,
        series_id: str,
        values: list[list[float]] | list[float],
        suggestion_id: str | None = None,
        proposer_config: Mapping[str, Any] | BoundaryProposerConfig | None = None,
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

        return SuggestionProposal(
            suggestionId=suggestion_id or f"suggestion-{series_id}",
            seriesId=series_id,
            modelVersion=self._model_version,
            seriesLength=proposal.seriesLength,
            channelCount=proposal.channelCount,
            candidateBoundaries=proposal.candidateBoundaries,
            provisionalSegments=proposal.provisionalSegments,
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
