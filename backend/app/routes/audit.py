from flask import Blueprint, current_app, jsonify, request

from app.services.audit_log import AuditLogError, AuditLogService, AuditSessionNotFoundError

audit_bp = Blueprint("audit", __name__)


def _get_audit_log_service() -> AuditLogService:
    return current_app.config.get("AUDIT_LOG_SERVICE") or AuditLogService()


@audit_bp.get("/api/audit/sessions/<session_id>/export")
def export_audit_session(session_id: str):
    try:
        payload = _get_audit_log_service().export_session(session_id)
    except AuditSessionNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404

    return jsonify(payload)


@audit_bp.post("/api/audit/sessions/<session_id>/suggestions/decision")
def log_suggestion_decision(session_id: str):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    required_fields = ("seriesId", "segmentationId", "suggestionId", "decision", "targetSegmentIds")
    missing_fields = [field_name for field_name in required_fields if field_name not in payload]
    if missing_fields:
        return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

    target_segment_ids = payload["targetSegmentIds"]
    if not isinstance(target_segment_ids, list) or any(not isinstance(item, str) for item in target_segment_ids):
        return jsonify({"error": "targetSegmentIds must be an array of strings."}), 400

    try:
        event_payload = _get_audit_log_service().log_suggestion_decision(
            session_id=session_id,
            series_id=str(payload["seriesId"]),
            segmentation_id=str(payload["segmentationId"]),
            suggestion_id=str(payload["suggestionId"]),
            decision=str(payload["decision"]),
            target_segment_ids=target_segment_ids,
            timestamp=str(payload["timestamp"]) if payload.get("timestamp") is not None else None,
            metadata=dict(payload.get("metadata") or {}),
        )
    except AuditLogError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(event_payload), 201
