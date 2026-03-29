import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.extensions import db
from app.models.audit_log import AuditEvent, AuditSession
from app.schemas.operation_results import OperationResultEnvelope


class AuditLogError(RuntimeError):
    """Raised when audit logging cannot be completed safely."""


class AuditSessionNotFoundError(AuditLogError):
    """Raised when a requested audit session does not exist."""


@dataclass(frozen=True)
class SuggestionDecision:
    suggestionId: str
    decision: str
    targetSegmentIds: tuple[str, ...]
    source: str = "model"

    def to_dict(self) -> dict[str, Any]:
        return {
            "suggestionId": self.suggestionId,
            "decision": self.decision,
            "targetSegmentIds": list(self.targetSegmentIds),
            "source": self.source,
        }


class AuditLogService:
    def create_session(
        self,
        *,
        session_id: str,
        series_id: str,
        segmentation_id: str,
        started_at: str | None = None,
    ) -> AuditSession:
        existing = db.session.get(AuditSession, session_id)
        if existing is not None:
            return existing

        session = AuditSession(
            session_id=session_id,
            series_id=series_id,
            segmentation_id=segmentation_id,
            started_at=started_at or _utc_now(),
            ended_at=None,
        )
        db.session.add(session)
        db.session.commit()
        return session

    def log_operation(
        self,
        *,
        session_id: str,
        operation: dict[str, Any],
        result: OperationResultEnvelope,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        normalized_timestamp = timestamp or _utc_now()
        session = self._get_or_create_session(
            session_id=session_id,
            series_id=str(operation["seriesId"]),
            segmentation_id=str(operation["segmentationId"]),
            started_at=normalized_timestamp,
        )
        event_type = "operation_applied" if result.applied else "operation_rejected"
        payload = {
            "eventId": self._next_event_id(session),
            "timestamp": normalized_timestamp,
            "eventType": event_type,
            "operation": dict(operation),
            "operationResult": result.to_dict(),
            "constraintEvaluation": (
                result.constraintEvaluation.to_dict() if result.constraintEvaluation is not None else None
            ),
            "metadata": self._build_operation_metadata(operation, result),
        }
        self._append_event(session, payload)
        return payload

    def log_suggestion_decision(
        self,
        *,
        session_id: str,
        series_id: str,
        segmentation_id: str,
        suggestion_id: str,
        decision: str,
        target_segment_ids: list[str] | tuple[str, ...],
        timestamp: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if decision not in {"accepted", "overridden"}:
            raise AuditLogError("Suggestion decision must be 'accepted' or 'overridden'.")

        normalized_timestamp = timestamp or _utc_now()
        session = self._get_or_create_session(
            session_id=session_id,
            series_id=series_id,
            segmentation_id=segmentation_id,
            started_at=normalized_timestamp,
        )
        suggestion = SuggestionDecision(
            suggestionId=suggestion_id,
            decision=decision,
            targetSegmentIds=tuple(str(segment_id) for segment_id in target_segment_ids),
        )
        payload = {
            "eventId": self._next_event_id(session),
            "timestamp": normalized_timestamp,
            "eventType": f"suggestion_{decision}",
            "suggestion": suggestion.to_dict(),
            "metadata": dict(metadata or {}),
        }
        self._append_event(session, payload)
        return payload

    def export_session(self, session_id: str) -> dict[str, Any]:
        session = db.session.get(AuditSession, session_id)
        if session is None:
            raise AuditSessionNotFoundError(f"Audit session '{session_id}' was not found.")

        events = [json.loads(event.payload_json) for event in session.events]
        return {
            "schemaVersion": "1.0.0",
            "sessionId": session.session_id,
            "seriesId": session.series_id,
            "segmentationId": session.segmentation_id,
            "startedAt": session.started_at,
            "endedAt": session.ended_at or session.started_at,
            "events": events,
        }

    def _get_or_create_session(
        self,
        *,
        session_id: str,
        series_id: str,
        segmentation_id: str,
        started_at: str,
    ) -> AuditSession:
        session = db.session.get(AuditSession, session_id)
        if session is not None:
            return session
        return self.create_session(
            session_id=session_id,
            series_id=series_id,
            segmentation_id=segmentation_id,
            started_at=started_at,
        )

    def _append_event(self, session: AuditSession, payload: dict[str, Any]) -> None:
        sequence = len(session.events) + 1
        event = AuditEvent(
            event_id=str(payload["eventId"]),
            session_id=session.session_id,
            sequence=sequence,
            timestamp=str(payload["timestamp"]),
            event_type=str(payload["eventType"]),
            payload_json=json.dumps(payload, ensure_ascii=True, sort_keys=True),
        )
        session.ended_at = str(payload["timestamp"])
        db.session.add(event)
        db.session.add(session)
        db.session.commit()

    def _next_event_id(self, session: AuditSession) -> str:
        return f"{session.session_id}-event-{len(session.events) + 1}"

    def _build_operation_metadata(
        self,
        operation: dict[str, Any],
        result: OperationResultEnvelope,
    ) -> dict[str, Any]:
        metadata = dict(result.metadata)
        metadata.setdefault("targetSegmentIds", list(operation.get("targetSegmentIds", [])))
        metadata["constraintOutcome"] = result.status
        metadata["applied"] = result.applied
        return metadata


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
