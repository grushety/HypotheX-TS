"""Op-invocation Flask blueprint (HTS-100).

Single endpoint: ``POST /api/operations/invoke``. The route stays thin
per CLAUDE.md "Routes are thin" — validate input, call
``invoke_service.invoke_operation``, return JSON. All op-specific logic
lives in the service module.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.schemas.operation_invoke import InvokeRequestError, OperationInvokeRequest
from app.services.operations.invoke_service import (
    IncompatibleOpError,
    MalformedParamsError,
    SegmentNotFoundError,
    UnknownOpError,
    invoke_operation,
)

operations_bp = Blueprint("operations", __name__)


@operations_bp.post("/api/operations/invoke")
def invoke():
    payload = request.get_json(silent=True)
    try:
        req = OperationInvokeRequest.from_json(payload)
    except InvokeRequestError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        response = invoke_operation(req)
    except UnknownOpError as exc:
        return jsonify({"error": str(exc)}), 400
    except SegmentNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except MalformedParamsError as exc:
        return jsonify({"error": str(exc)}), 400
    except IncompatibleOpError as exc:
        return jsonify({"error": str(exc)}), 422

    return jsonify(response.to_dict()), 200
