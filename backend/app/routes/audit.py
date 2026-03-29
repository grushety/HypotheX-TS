from flask import Blueprint, current_app, jsonify

from app.services.audit_log import AuditLogService, AuditSessionNotFoundError

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
