from dataclasses import dataclass
from typing import Any

from app.core.domain_config import DomainConfig, load_domain_config
from app.domain.chunk_scoring import compute_chunk_scores
from app.domain.stats import SegmentStatistics


@dataclass(frozen=True)
class ChunkAssignment:
    schemaVersion: str
    ontologyName: str
    assignedLabel: str
    confidence: float
    isAmbiguous: bool
    ambiguityMargin: float
    runnerUpLabel: str | None
    scores: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schemaVersion,
            "ontologyName": self.ontologyName,
            "assignedLabel": self.assignedLabel,
            "confidence": self.confidence,
            "isAmbiguous": self.isAmbiguous,
            "ambiguityMargin": self.ambiguityMargin,
            "runnerUpLabel": self.runnerUpLabel,
            "scores": dict(self.scores),
        }

    def to_segment_payload(
        self,
        *,
        segment_id: str,
        start_index: int,
        end_index: int,
        provenance: str = "model",
    ) -> dict[str, Any]:
        return {
            "segmentId": segment_id,
            "startIndex": start_index,
            "endIndex": end_index,
            "label": self.assignedLabel,
            "confidence": self.confidence,
            "provenance": provenance,
        }


def assign_chunk_type(
    statistics: SegmentStatistics | dict[str, Any],
    *,
    domain_config: DomainConfig | None = None,
    ambiguity_margin: float | None = None,
) -> ChunkAssignment:
    config = domain_config or load_domain_config()
    chunk_scores = compute_chunk_scores(statistics, domain_config=config)
    sorted_scores = sorted(
        chunk_scores.scores.items(),
        key=lambda item: (-item[1], config.active_chunk_types.index(item[0])),
    )

    top_label, top_score = sorted_scores[0]
    runner_up_label: str | None = None
    runner_up_score = 0.0
    if len(sorted_scores) > 1:
        runner_up_label, runner_up_score = sorted_scores[1]

    resolved_margin = (
        float(ambiguity_margin)
        if ambiguity_margin is not None
        else float(config.thresholds["ambiguityMarginMin"])
    )
    score_margin = float(top_score - runner_up_score)

    return ChunkAssignment(
        schemaVersion="1.0.0",
        ontologyName=config.ontology_name,
        assignedLabel=top_label,
        confidence=float(top_score),
        isAmbiguous=score_margin < resolved_margin,
        ambiguityMargin=score_margin,
        runnerUpLabel=runner_up_label,
        scores=dict(chunk_scores.scores),
    )
