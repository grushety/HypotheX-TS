from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TelemetryMetricCheck:
    metric_id: str
    description: str
    status: str
    available_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "metricId": self.metric_id,
            "description": self.description,
            "status": self.status,
            "availableFields": list(self.available_fields),
            "missingFields": list(self.missing_fields),
            "note": self.note,
        }


@dataclass(frozen=True)
class TelemetryValidationReport:
    schema_version: str
    session_id: str
    checks: tuple[TelemetryMetricCheck, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "sessionId": self.session_id,
            "checks": [check.to_dict() for check in self.checks],
        }


def validate_session_telemetry(session_log: dict[str, Any]) -> TelemetryValidationReport:
    session_id = str(session_log.get("sessionId", ""))
    events = session_log.get("events", [])
    if not isinstance(events, list):
        events = []

    checks = (
        _build_check(
            metric_id="session_duration",
            description="Session duration and completion timing",
            available_fields=_present_top_level_fields(session_log, ("startedAt", "endedAt")),
            required_fields=("startedAt", "endedAt"),
            note="Enough for coarse session duration, but not enough for per-task completion without task markers.",
        ),
        _build_check(
            metric_id="operation_diversity",
            description="Diversity of operation types used during the session",
            available_fields=_present_event_fields(events, ("eventType", "operation.operationType")),
            required_fields=("eventType", "operation.operationType"),
            note="Supports counting distinct semantic operations across a session.",
        ),
        _build_check(
            metric_id="constraint_feedback_rate",
            description="Rate of warning or failure encounters during user actions",
            available_fields=_present_event_fields(events, ("constraintEvaluation.status", "operationResult.status")),
            required_fields=("constraintEvaluation.status",),
            note="OperationResult.status is a fallback when constraintEvaluation is omitted.",
        ),
        _build_check(
            metric_id="suggestion_uptake",
            description="Model suggestion acceptance and override behavior",
            available_fields=_present_event_fields(events, ("suggestion.decision", "suggestion.suggestionId")),
            required_fields=("suggestion.decision",),
            note="Only meaningful in semantic-interface sessions where suggestions are permitted.",
        ),
        _build_check(
            metric_id="target_segment_coverage",
            description="Coverage of edited segments across a session",
            available_fields=_present_event_fields(events, ("metadata.targetSegmentIds", "operation.targetSegmentIds")),
            required_fields=("operation.targetSegmentIds",),
            note="Supports segment-touch counts but not viewport or dwell-based coverage.",
        ),
        _build_check(
            metric_id="condition_assignment",
            description="Explicit condition label for baseline versus semantic comparison",
            available_fields=_present_top_level_fields(session_log, ("conditionId",)),
            required_fields=("conditionId",),
            note="Missing today. Condition is not encoded directly in the session export and must be attached externally.",
        ),
        _build_check(
            metric_id="participant_linkage",
            description="Participant-level linkage across multiple sessions",
            available_fields=_present_top_level_fields(session_log, ("participantId",)),
            required_fields=("participantId",),
            note="Missing today. Pilot analysis must currently attach participant IDs outside the exported session log.",
        ),
        _build_check(
            metric_id="task_completion_marker",
            description="Task-level success and completion markers",
            available_fields=_present_top_level_fields(session_log, ("taskId", "taskCompletedAt", "taskOutcome")),
            required_fields=("taskId", "taskOutcome"),
            note="Missing today. Later study preparation should add explicit task metadata rather than infer completion implicitly.",
        ),
    )
    return TelemetryValidationReport(
        schema_version="1.0.0",
        session_id=session_id,
        checks=checks,
    )


def compare_condition_event_coverage(
    semantic_session: dict[str, Any],
    baseline_session: dict[str, Any],
) -> dict[str, Any]:
    semantic_event_types = _sorted_unique_event_types(semantic_session)
    baseline_event_types = _sorted_unique_event_types(baseline_session)
    return {
        "semanticEventTypes": semantic_event_types,
        "baselineEventTypes": baseline_event_types,
        "semanticOnlyEventTypes": sorted(set(semantic_event_types) - set(baseline_event_types)),
        "sharedEventTypes": sorted(set(semantic_event_types) & set(baseline_event_types)),
    }


def _present_top_level_fields(payload: dict[str, Any], field_names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(field_name for field_name in field_names if field_name in payload and payload.get(field_name) not in (None, ""))


def _present_event_fields(events: list[Any], field_names: tuple[str, ...]) -> tuple[str, ...]:
    present: list[str] = []
    for field_name in field_names:
        if any(_field_exists(event, field_name) for event in events if isinstance(event, dict)):
            present.append(field_name)
    return tuple(present)


def _field_exists(payload: dict[str, Any], dotted_field: str) -> bool:
    current: Any = payload
    for part in dotted_field.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return current not in (None, "")


def _build_check(
    *,
    metric_id: str,
    description: str,
    available_fields: tuple[str, ...],
    required_fields: tuple[str, ...],
    note: str,
) -> TelemetryMetricCheck:
    missing_fields = tuple(field_name for field_name in required_fields if field_name not in available_fields)
    status = "supported" if not missing_fields else "missing_fields"
    return TelemetryMetricCheck(
        metric_id=metric_id,
        description=description,
        status=status,
        available_fields=available_fields,
        missing_fields=missing_fields,
        note=note,
    )


def _sorted_unique_event_types(session_log: dict[str, Any]) -> list[str]:
    events = session_log.get("events", [])
    if not isinstance(events, list):
        return []
    return sorted({str(event.get("eventType")) for event in events if isinstance(event, dict) and event.get("eventType")})
