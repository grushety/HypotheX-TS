from dataclasses import dataclass
from typing import Any

from app.core.domain_config import DomainConfig, load_domain_config
from app.domain.stats import SegmentStatistics


class ChunkScoringError(RuntimeError):
    """Raised when chunk scores cannot be computed safely."""


@dataclass(frozen=True)
class ChunkScores:
    schemaVersion: str
    ontologyName: str
    scores: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schemaVersion,
            "ontologyName": self.ontologyName,
            "scores": dict(self.scores),
        }


def compute_chunk_scores(
    statistics: SegmentStatistics | dict[str, Any],
    *,
    domain_config: DomainConfig | None = None,
) -> ChunkScores:
    stats = _coerce_statistics(statistics)
    config = domain_config or load_domain_config()
    thresholds = config.thresholds
    duration_limits = config.duration_limits

    slope_abs = abs(stats.slope)

    periodic_score = _average(
        _minimum_duration_score(stats.segmentLength, duration_limits["periodicMinLength"]),
        _ratio_score(stats.periodicityScore, thresholds["periodicityScoreMin"]),
        _inverse_ratio_score(stats.peakScore, thresholds["peakScoreMin"] * 2.0),
    )

    spike_score = _average(
        _maximum_duration_score(stats.segmentLength, duration_limits["spikeMaxLength"]),
        _ratio_score(stats.peakScore, thresholds["peakScoreMin"]),
        _ratio_score(stats.contextContrast, thresholds["contextContrastMin"]),
    )

    trend_score = _average(
        _ratio_score(slope_abs, thresholds["slopeAbsMin"]),
        _ratio_score(stats.signConsistency, thresholds["signConsistencyMin"]),
        _inverse_ratio_score(stats.residualToLine, thresholds["residualToLineMax"]),
    )

    plateau_score = _average(
        _inverse_ratio_score(slope_abs, thresholds["slopeAbsMin"] * 2.0),
        _inverse_ratio_score(stats.variance, thresholds["varianceMax"]),
        _inverse_ratio_score(stats.periodicityScore, thresholds["periodicityScoreMin"]),
    )

    event_base_score = _average(
        _bounded_duration_score(
            stats.segmentLength,
            duration_limits["eventMinLength"],
            duration_limits["eventMaxLength"],
        ),
        _ratio_score(stats.contextContrast, thresholds["contextContrastMin"]),
    )
    event_score = _clamp01(event_base_score * (1.0 - 0.35 * max(spike_score, periodic_score)))

    transition_score = _average(
        _minimum_duration_score(stats.segmentLength, duration_limits["transitionMinLength"]),
        _ratio_score(stats.contextContrast, thresholds["contextContrastMin"]),
        _ratio_score(slope_abs, thresholds["slopeAbsMin"]),
    )

    computed_scores = {
        "trend": trend_score,
        "plateau": plateau_score,
        "spike": spike_score,
        "event": event_score,
        "transition": transition_score,
        "periodic": periodic_score,
    }

    return ChunkScores(
        schemaVersion="1.0.0",
        ontologyName=config.ontology_name,
        scores={chunk_type: computed_scores[chunk_type] for chunk_type in config.active_chunk_types},
    )


def _coerce_statistics(statistics: SegmentStatistics | dict[str, Any]) -> SegmentStatistics:
    if isinstance(statistics, SegmentStatistics):
        return statistics
    if not isinstance(statistics, dict):
        raise ChunkScoringError("Chunk scoring requires SegmentStatistics or a compatible dict payload.")

    required_fields = {
        "schemaVersion",
        "seriesLength",
        "startIndex",
        "endIndex",
        "segmentLength",
        "channelCount",
        "mean",
        "variance",
        "slope",
        "signConsistency",
        "residualToLine",
        "contextContrast",
        "peakScore",
        "periodicityScore",
    }
    missing_fields = sorted(required_fields - set(statistics))
    if missing_fields:
        raise ChunkScoringError(f"Chunk scoring statistics are missing required fields: {missing_fields}")

    return SegmentStatistics(
        schemaVersion=str(statistics["schemaVersion"]),
        seriesLength=int(statistics["seriesLength"]),
        startIndex=int(statistics["startIndex"]),
        endIndex=int(statistics["endIndex"]),
        segmentLength=int(statistics["segmentLength"]),
        channelCount=int(statistics["channelCount"]),
        mean=tuple(float(value) for value in statistics["mean"]),
        variance=float(statistics["variance"]),
        slope=float(statistics["slope"]),
        signConsistency=float(statistics["signConsistency"]),
        residualToLine=float(statistics["residualToLine"]),
        contextContrast=float(statistics["contextContrast"]),
        peakScore=float(statistics["peakScore"]),
        periodicityScore=float(statistics["periodicityScore"]),
    )


def _ratio_score(value: float, threshold: float) -> float:
    _validate_threshold(threshold)
    return _clamp01(value / threshold)


def _inverse_ratio_score(value: float, threshold: float) -> float:
    _validate_threshold(threshold)
    return _clamp01(1.0 - (value / threshold))


def _minimum_duration_score(length: int, minimum_length: int) -> float:
    if minimum_length < 1:
        raise ChunkScoringError("Minimum duration thresholds must be at least 1.")
    return _clamp01(length / minimum_length)


def _maximum_duration_score(length: int, maximum_length: int) -> float:
    if maximum_length < 1:
        raise ChunkScoringError("Maximum duration thresholds must be at least 1.")
    if length <= maximum_length:
        return 1.0
    overflow = length - maximum_length
    return _clamp01(1.0 - (overflow / maximum_length))


def _bounded_duration_score(length: int, minimum_length: int, maximum_length: int) -> float:
    if minimum_length < 1 or maximum_length < minimum_length:
        raise ChunkScoringError("Bounded duration thresholds must define a valid positive range.")
    if minimum_length <= length <= maximum_length:
        return 1.0
    if length < minimum_length:
        return _minimum_duration_score(length, minimum_length)

    overflow = length - maximum_length
    window = max(1, maximum_length - minimum_length + 1)
    return _clamp01(1.0 - (overflow / window))


def _average(*values: float) -> float:
    if not values:
        raise ChunkScoringError("Chunk score averages require at least one value.")
    return float(sum(values) / len(values))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _validate_threshold(threshold: float) -> None:
    if threshold <= 0:
        raise ChunkScoringError("Chunk scoring thresholds must be positive.")
