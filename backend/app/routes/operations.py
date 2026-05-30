"""Op-invocation Flask blueprint (HTS-100, REWORK-07).

Endpoints:
  - ``POST /api/operations/invoke`` — per-operation invocation (HTS-100).
  - ``POST /api/operations/min-flip`` — closed-form smallest-edit probe
    that flips the prototype classifier (REWORK-07).

The route stays thin per CLAUDE.md "Routes are thin" — validate input,
call the service, return JSON.
"""
from __future__ import annotations

import math

from flask import Blueprint, current_app, jsonify, request

from app.schemas.operation_invoke import InvokeRequestError, OperationInvokeRequest
from app.services.models import ModelArtifactNotFoundError, ModelRegistry, ModelRegistryError
from app.services.operations.invoke_service import (
    IncompatibleOpError,
    MalformedParamsError,
    SegmentNotFoundError,
    UnknownOpError,
    invoke_operation,
)
from app.services.operations.min_flip import MinFlipService, MinFlipServiceError

operations_bp = Blueprint("operations", __name__)

# Cap mirrors the predict-values + plausibility-gauges endpoints.
_MAX_VALUES = 65_536


def _get_min_flip_service() -> MinFlipService:
    return current_app.config.get("MIN_FLIP_SERVICE") or MinFlipService(
        model_registry=current_app.config.get("MODEL_REGISTRY") or ModelRegistry(),
    )


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


@operations_bp.post("/api/operations/min-flip")
def min_flip():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    artifact_id = body.get("artifact_id")
    baseline_values = body.get("baseline_values")

    if not isinstance(artifact_id, str) or not artifact_id:
        return jsonify({"error": "Field 'artifact_id' is required and must be a non-empty string."}), 400
    if not isinstance(baseline_values, list) or not baseline_values:
        return jsonify({"error": "Field 'baseline_values' is required and must be a non-empty array."}), 400
    if len(baseline_values) > _MAX_VALUES:
        return (
            jsonify({"error": f"Field 'baseline_values' must not exceed {_MAX_VALUES} entries."}),
            400,
        )
    if not all(
        isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        for value in baseline_values
    ):
        return jsonify({"error": "Field 'baseline_values' must contain only finite numbers."}), 400

    service = _get_min_flip_service()
    try:
        result = service.find_minimal_flip(
            artifact_id=artifact_id,
            baseline_values=baseline_values,
        )
    except MinFlipServiceError as exc:
        return jsonify({"error": str(exc)}), 400
    except ModelArtifactNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except ModelRegistryError as exc:
        return jsonify({"error": str(exc)}), 500

    return (
        jsonify(
            {
                "found": result.found,
                "artifact_id": result.artifact_id,
                "baseline_class": result.baseline_class,
                "flipped_class": result.flipped_class,
                "distance": result.distance,
                "edit_values": list(result.edit_values),
                "method": result.method,
                "reference": result.reference,
                "reason": result.reason,
            }
        ),
        200,
    )
