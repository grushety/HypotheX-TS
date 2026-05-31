"""Cohort confirmation Flask blueprint (REWORK-10).

Single endpoint: ``POST /api/cohort/apply``. Validates input then
delegates to :class:`CohortService`. Per CLAUDE.md "Routes are thin" —
no aggregation logic here.
"""

from __future__ import annotations

import math

from flask import Blueprint, current_app, jsonify, request

from app.services.cohort import CohortService, CohortServiceError
from app.services.datasets import (
    DatasetNotFoundError,
    DatasetRegistry,
    DatasetRegistryError,
)
from app.services.inference import InferenceAdapterError, InferenceServiceError
from app.services.models import ModelArtifactNotFoundError, ModelRegistry, ModelRegistryError

cohort_bp = Blueprint("cohort", __name__)

_MAX_COHORT_SIZE = 64


def _get_cohort_service() -> CohortService:
    return current_app.config.get("COHORT_SERVICE") or CohortService(
        dataset_registry=current_app.config.get("DATASET_REGISTRY") or DatasetRegistry(),
        prediction_service=current_app.config.get("PREDICTION_SERVICE"),
    )


@cohort_bp.post("/api/cohort/apply")
def apply_cohort():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    artifact_id = body.get("artifact_id")
    dataset_name = body.get("dataset")
    split = body.get("split")
    sample_indices = body.get("sample_indices")
    op_name = body.get("op_name")
    op_params = body.get("op_params") or {}

    if not isinstance(artifact_id, str) or not artifact_id:
        return jsonify({"error": "Field 'artifact_id' is required and must be a non-empty string."}), 400
    if not isinstance(dataset_name, str) or not dataset_name:
        return jsonify({"error": "Field 'dataset' is required and must be a non-empty string."}), 400
    if split not in ("train", "test"):
        return jsonify({"error": "Field 'split' must be 'train' or 'test'."}), 400
    if not isinstance(sample_indices, list) or not sample_indices:
        return jsonify({"error": "Field 'sample_indices' is required and must be a non-empty array."}), 400
    if len(sample_indices) > _MAX_COHORT_SIZE:
        return (
            jsonify({"error": f"Field 'sample_indices' must not exceed {_MAX_COHORT_SIZE} entries."}),
            400,
        )
    cleaned_indices: list[int] = []
    for index in sample_indices:
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            return jsonify({"error": "Field 'sample_indices' must contain non-negative integers."}), 400
        cleaned_indices.append(index)
    if not isinstance(op_name, str) or op_name not in ("amplify", "shift"):
        return (
            jsonify({"error": "Field 'op_name' must be one of 'amplify', 'shift'."}),
            400,
        )
    if not isinstance(op_params, dict):
        return jsonify({"error": "Field 'op_params' must be an object."}), 400
    for key, value in op_params.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool) and not math.isfinite(value):
            return (
                jsonify({"error": f"op_params.{key} must be a finite number."}),
                400,
            )

    service = _get_cohort_service()
    try:
        result = service.apply(
            artifact_id=artifact_id,
            dataset_name=dataset_name,
            split=split,
            sample_indices=cleaned_indices,
            op_name=op_name,
            op_params=op_params,
        )
    except CohortServiceError as exc:
        return jsonify({"error": str(exc)}), 400
    except DatasetNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except ModelArtifactNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except (InferenceAdapterError, InferenceServiceError) as exc:
        return jsonify({"error": str(exc)}), 400
    except (DatasetRegistryError, ModelRegistryError) as exc:
        return jsonify({"error": str(exc)}), 500

    aggregates = result.aggregates
    return (
        jsonify(
            {
                "artifact_id": result.artifact_id,
                "dataset_name": result.dataset_name,
                "split": result.split,
                "op_name": result.op_name,
                "op_params": result.op_params,
                "method": result.method,
                "reference": result.reference,
                "per_series": [
                    {
                        "sample_index": s.sample_index,
                        "baseline_class": s.baseline_class,
                        "current_class": s.current_class,
                        "baseline_prob": s.baseline_prob,
                        "current_prob": s.current_prob,
                        "delta": s.delta,
                        "flipped": s.flipped,
                    }
                    for s in result.per_series
                ],
                "aggregates": {
                    "total": aggregates.total,
                    "flipped_count": aggregates.flipped_count,
                    "flip_rate": aggregates.flip_rate,
                    "flip_rate_ci": {
                        "lower": aggregates.flip_rate_ci.lower,
                        "upper": aggregates.flip_rate_ci.upper,
                        "confidence_level": aggregates.flip_rate_ci.confidence_level,
                        "iterations": aggregates.flip_rate_ci.iterations,
                    },
                    "mean_delta": aggregates.mean_delta,
                    "mean_delta_ci": {
                        "lower": aggregates.mean_delta_ci.lower,
                        "upper": aggregates.mean_delta_ci.upper,
                        "confidence_level": aggregates.mean_delta_ci.confidence_level,
                        "iterations": aggregates.mean_delta_ci.iterations,
                    },
                    "delta_histogram_bin_edges": list(aggregates.delta_histogram_bin_edges),
                    "delta_histogram_counts": list(aggregates.delta_histogram_counts),
                    "biggest_mover_index": aggregates.biggest_mover_index,
                },
            }
        ),
        200,
    )
