from flask import Blueprint, current_app, jsonify

from app.services.health import build_health_payload

health_bp = Blueprint("health", __name__)


@health_bp.get("/api/health")
def health_check():
    payload = build_health_payload(current_app.config)
    return jsonify(payload)
