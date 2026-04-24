from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.suggestion.boundary_proposal import BoundaryCandidate, BoundaryProposerConfig, ProvisionalSegment


@dataclass(frozen=True)
class SuggestionProposal:
    suggestionId: str
    seriesId: str
    modelVersion: str
    seriesLength: int
    channelCount: int
    candidateBoundaries: tuple[BoundaryCandidate, ...]
    provisionalSegments: tuple[ProvisionalSegment, ...]
    proposerName: str
    proposerConfig: BoundaryProposerConfig
    boundary_uncertainty: tuple[float, ...] | None = None
    segment_uncertainty: tuple[float, ...] | None = None
    labeler: str = "prototype"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schemaVersion": "1.0.0",
            "suggestionId": self.suggestionId,
            "seriesId": self.seriesId,
            "modelVersion": self.modelVersion,
            "seriesLength": self.seriesLength,
            "channelCount": self.channelCount,
            "candidateBoundaries": [candidate.to_dict() for candidate in self.candidateBoundaries],
            "provisionalSegments": [segment.to_dict() for segment in self.provisionalSegments],
            "boundaryProposer": {
                "name": self.proposerName,
                "config": {
                    "windowSize": self.proposerConfig.window_size,
                    "minSegmentLength": self.proposerConfig.min_segment_length,
                    "scoreThreshold": self.proposerConfig.score_threshold,
                    "maxBoundaries": self.proposerConfig.max_boundaries,
                },
            },
        }
        if self.boundary_uncertainty is not None:
            payload["boundaryUncertainty"] = list(self.boundary_uncertainty)
        if self.segment_uncertainty is not None:
            payload["segmentUncertainty"] = list(self.segment_uncertainty)
        payload["labeler"] = self.labeler
        return payload
