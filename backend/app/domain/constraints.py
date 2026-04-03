from dataclasses import dataclass
from typing import Any

from app.core.domain_config import DomainConfig, load_domain_config
from app.domain.stats import SegmentStatisticsError, compute_segment_statistics


@dataclass(frozen=True)
class ConstraintTargetSegment:
    segment_id: str
    start_index: int
    end_index: int
    label: str

    @property
    def length(self) -> int:
        return self.end_index - self.start_index + 1


@dataclass(frozen=True)
class ConstraintViolation:
    constraintId: str
    severity: str
    message: str
    affectedSegmentIds: tuple[str, ...] = ()
    repairHint: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "constraintId": self.constraintId,
            "severity": self.severity,
            "message": self.message,
        }
        if self.affectedSegmentIds:
            payload["affectedSegmentIds"] = list(self.affectedSegmentIds)
        if self.repairHint is not None:
            payload["repairHint"] = dict(self.repairHint)
        return payload


def evaluate_constraints(
    series: Any,
    segments: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    domain_config: DomainConfig | None = None,
    constraint_mode: str | None = None,
) -> tuple[ConstraintViolation, ...]:
    config = domain_config or load_domain_config()
    normalized_segments = _coerce_segments(segments)

    violations: list[ConstraintViolation] = []
    violations.extend(
        evaluate_minimum_segment_duration(
            normalized_segments,
            domain_config=config,
            constraint_mode=constraint_mode,
        )
    )
    violations.extend(
        evaluate_monotonic_trend_consistency(
            series,
            normalized_segments,
            domain_config=config,
            constraint_mode=constraint_mode,
        )
    )
    violations.extend(
        evaluate_plateau_stability(
            series,
            normalized_segments,
            domain_config=config,
            constraint_mode=constraint_mode,
        )
    )
    violations.extend(
        evaluate_label_compatibility(
            normalized_segments,
            domain_config=config,
            constraint_mode=constraint_mode,
        )
    )
    return tuple(violations)


def evaluate_minimum_segment_duration(
    segments: tuple[ConstraintTargetSegment, ...],
    *,
    domain_config: DomainConfig | None = None,
    constraint_mode: str | None = None,
) -> tuple[ConstraintViolation, ...]:
    config = domain_config or load_domain_config()
    minimum_length = config.duration_limits["minimumSegmentLength"]
    severity = _resolve_severity("minimum_segment_duration", config, constraint_mode)

    violations = [
        ConstraintViolation(
            constraintId="minimum_segment_duration",
            severity=severity,
            message=(
                f"Segment '{segment.segment_id}' would be shorter than the minimum duration "
                f"of {minimum_length} steps."
            ),
            affectedSegmentIds=(segment.segment_id,),
            repairHint={
                "minimumLength": minimum_length,
                "suggestedAction": "extend_or_merge",
            },
        )
        for segment in segments
        if segment.length < minimum_length
    ]
    return tuple(violations)


def evaluate_monotonic_trend_consistency(
    series: Any,
    segments: tuple[ConstraintTargetSegment, ...],
    *,
    domain_config: DomainConfig | None = None,
    constraint_mode: str | None = None,
) -> tuple[ConstraintViolation, ...]:
    config = domain_config or load_domain_config()
    severity = _resolve_severity("monotonic_trend_consistency", config, constraint_mode)
    slope_min = config.thresholds["slopeAbsMin"]
    sign_min = config.thresholds["signConsistencyMin"]
    residual_max = config.thresholds["residualToLineMax"]

    violations: list[ConstraintViolation] = []
    for segment in segments:
        if segment.label != "trend" or segment.length < 2:
            continue

        try:
            statistics = compute_segment_statistics(
                series,
                segment.start_index,
                segment.end_index,
                min_segment_length=1,
            )
        except SegmentStatisticsError:
            continue

        if (
            abs(statistics.slope) >= slope_min
            and statistics.signConsistency >= sign_min
            and statistics.residualToLine <= residual_max
        ):
            continue

        violations.append(
            ConstraintViolation(
                constraintId="monotonic_trend_consistency",
                severity=severity,
                message=(
                    f"Trend segment '{segment.segment_id}' is not sufficiently monotonic "
                    f"under the current slope, sign-consistency, and residual thresholds."
                ),
                affectedSegmentIds=(segment.segment_id,),
                repairHint={
                    "suggestedAction": "adjust_boundary_or_reclassify",
                    "requiredSlopeAbsMin": slope_min,
                    "requiredSignConsistencyMin": sign_min,
                    "requiredResidualToLineMax": residual_max,
                },
            )
        )

    return tuple(violations)


def evaluate_plateau_stability(
    series: Any,
    segments: tuple[ConstraintTargetSegment, ...],
    *,
    domain_config: DomainConfig | None = None,
    constraint_mode: str | None = None,
) -> tuple[ConstraintViolation, ...]:
    config = domain_config or load_domain_config()
    severity = _resolve_severity("plateau_stability", config, constraint_mode)
    periodic_min_length = config.duration_limits["periodicMinLength"]
    slope_min = config.thresholds["slopeAbsMin"]
    variance_max = config.thresholds["varianceMax"]
    periodicity_min = config.thresholds["periodicityScoreMin"]

    violations: list[ConstraintViolation] = []
    for segment in segments:
        if segment.label != "plateau" or segment.length < 2:
            continue

        try:
            statistics = compute_segment_statistics(
                series,
                segment.start_index,
                segment.end_index,
                min_segment_length=1,
            )
        except SegmentStatisticsError:
            continue

        periodicity_ok = (
            statistics.segmentLength < periodic_min_length
            or statistics.periodicityScore < periodicity_min
        )
        if (
            abs(statistics.slope) < slope_min
            and statistics.variance <= variance_max
            and periodicity_ok
        ):
            continue

        violations.append(
            ConstraintViolation(
                constraintId="plateau_stability",
                severity=severity,
                message=(
                    f"Plateau segment '{segment.segment_id}' is not stable enough to remain a plateau "
                    f"under the current slope, variance, or periodicity thresholds."
                ),
                affectedSegmentIds=(segment.segment_id,),
                repairHint={
                    "suggestedAction": "reclassify_or_smooth",
                    "requiredSlopeAbsMax": slope_min,
                    "requiredVarianceMax": variance_max,
                    "requiredPeriodicityMax": periodicity_min,
                    "periodicityAppliesAtLength": periodic_min_length,
                },
            )
        )

    return tuple(violations)


def evaluate_label_compatibility(
    segments: tuple[ConstraintTargetSegment, ...],
    *,
    domain_config: DomainConfig | None = None,
    constraint_mode: str | None = None,
) -> tuple[ConstraintViolation, ...]:
    config = domain_config or load_domain_config()
    severity = _resolve_severity("label_compatibility", config, constraint_mode)

    ordered_segments = tuple(sorted(segments, key=lambda segment: segment.start_index))
    violations: list[ConstraintViolation] = []
    for left_segment, right_segment in zip(ordered_segments, ordered_segments[1:]):
        if left_segment.label == "event" and right_segment.label == "event":
            violations.append(
                ConstraintViolation(
                    constraintId="label_compatibility",
                    severity=severity,
                    message=(
                        f"Adjacent event segments '{left_segment.segment_id}' and "
                        f"'{right_segment.segment_id}' should be merged or separated by a transition."
                    ),
                    affectedSegmentIds=(left_segment.segment_id, right_segment.segment_id),
                    repairHint={
                        "suggestedAction": "merge_or_insert_transition",
                    },
                )
            )

    return tuple(violations)


def _coerce_segments(segments: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> tuple[ConstraintTargetSegment, ...]:
    normalized_segments: list[ConstraintTargetSegment] = []
    for payload in segments:
        normalized_segments.append(
            ConstraintTargetSegment(
                segment_id=str(payload["segmentId"]),
                start_index=int(payload["startIndex"]),
                end_index=int(payload["endIndex"]),
                label=str(payload["label"]),
            )
        )
    return tuple(normalized_segments)


def _resolve_severity(
    constraint_id: str,
    domain_config: DomainConfig,
    constraint_mode: str | None,
) -> str:
    if constraint_mode is not None:
        if constraint_mode not in {"soft", "hard"}:
            raise ValueError(f"Unsupported constraint mode '{constraint_mode}'.")
        return constraint_mode
    return domain_config.get_constraint_default(constraint_id).default_mode
