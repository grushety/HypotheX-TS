"""Donor-proposal blueprint (HTS-104).

Single endpoint: ``POST /api/donors/propose``. Frontend ``donorApi.js``
defines the on-the-wire contract; this route satisfies it.

Backends:
  ``NativeGuide``   — DTW nearest-unlike-neighbour via OP-012 NativeGuide
                       engine; ranks training-corpus members of
                       ``target_class`` by DTW distance to the segment;
                       returns the candidate at offset ``k`` (after
                       removing ``exclude_ids``).
  ``SETSDonor`` /
  ``DiscordDonor`` /
  ``TimeGAN`` /
  ``ShapeDBA``      — Not yet supported on this route. Returns 501 with the
                       ``supported`` list so the frontend's "coming soon"
                       warning fires correctly.
  ``UserDrawn``     — Frontend bypasses the network and inlines the
                       sketchpad values into the op call. Returns 400 if a
                       request reaches this route by mistake.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
from flask import Blueprint, current_app, jsonify, request

from app.services.datasets import (
    DatasetNotFoundError,
    DatasetRegistry,
    DatasetRegistryError,
)

logger = logging.getLogger(__name__)

donors_bp = Blueprint("donors", __name__)


_SUPPORTED_BACKENDS = ("NativeGuide", "UserDrawn")
_NOT_IMPLEMENTED_BACKENDS = frozenset({"SETSDonor", "DiscordDonor", "TimeGAN", "ShapeDBA"})


def _get_dataset_registry() -> DatasetRegistry:
    return current_app.config.get("DATASET_REGISTRY") or DatasetRegistry()


@donors_bp.post("/api/donors/propose")
def propose_donor():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    backend = payload.get("backend")
    segment_values = payload.get("segment_values")
    target_class = payload.get("target_class")
    dataset_name = payload.get("dataset")

    if not isinstance(backend, str) or not backend:
        return jsonify({"error": "backend is required and must be a string."}), 400
    if not isinstance(segment_values, list) or not segment_values:
        return jsonify({"error": "segment_values must be a non-empty list."}), 400
    if not all(isinstance(v, (int, float)) for v in segment_values):
        return jsonify({"error": "segment_values must contain only numbers."}), 400
    if target_class is None or (isinstance(target_class, str) and not target_class):
        return jsonify({"error": "target_class is required."}), 400

    if backend in _NOT_IMPLEMENTED_BACKENDS:
        return jsonify({
            "error": f"{backend} not yet supported",
            "supported": list(_SUPPORTED_BACKENDS),
        }), 501

    if backend == "UserDrawn":
        return jsonify({
            "error": "UserDrawn donors are inlined client-side; this route is not used.",
        }), 400

    if backend != "NativeGuide":
        return jsonify({"error": f"Unknown backend: {backend!r}"}), 400

    if not isinstance(dataset_name, str) or not dataset_name:
        return jsonify({
            "error": "NativeGuide requires a 'dataset' field naming the training corpus.",
        }), 400

    try:
        k = int(payload.get("k", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "k must be a non-negative integer."}), 400
    if k < 0:
        return jsonify({"error": "k must be a non-negative integer."}), 400

    exclude_ids_raw = payload.get("exclude_ids", [])
    if not isinstance(exclude_ids_raw, list) or not all(
        isinstance(s, str) for s in exclude_ids_raw
    ):
        return jsonify({"error": "exclude_ids must be an array of strings."}), 400
    exclude_ids = frozenset(exclude_ids_raw)

    try:
        registry = _get_dataset_registry()
        dataset = registry.load_dataset(dataset_name)
    except DatasetNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except DatasetRegistryError as exc:
        return jsonify({"error": str(exc)}), 400

    candidates = _native_guide_rank(
        dataset,
        np.asarray(segment_values, dtype=np.float64),
        str(target_class),
        k=k,
        exclude_ids=exclude_ids,
    )

    return jsonify({
        "backend": backend,
        "candidates": candidates,
    }), 200


def _native_guide_rank(
    dataset: Any,
    target_segment: np.ndarray,
    target_class: str,
    *,
    k: int,
    exclude_ids: frozenset[str],
) -> list[dict[str, Any]]:
    """Rank training-corpus candidates by DTW distance and return the one at offset k.

    Returns a list of length 0 (when k is past the end of the ranked list)
    or 1 (the candidate at offset k after removing exclude_ids). Mirrors
    the DonorPicker's "one at a time, walked via k" behaviour.
    """
    from tslearn.metrics import dtw as tslearn_dtw  # noqa: PLC0415

    classes = dataset.summary.classes
    train_series = dataset.train_series
    train_labels = dataset.train_labels

    series_2d = train_series.reshape(train_series.shape[0], -1)

    ranked: list[tuple[float, int, str, list[float]]] = []
    for idx in range(series_2d.shape[0]):
        label_index = int(train_labels[idx])
        if label_index < 0 or label_index >= len(classes):
            continue
        if classes[label_index] != target_class:
            continue
        donor_id = f"native_guide:{idx}"
        if donor_id in exclude_ids:
            continue
        donor_values = series_2d[idx].astype(np.float64)
        try:
            distance = float(tslearn_dtw(target_segment, donor_values))
        except Exception as exc:  # noqa: BLE001
            logger.warning("DTW failed for donor %s: %s", donor_id, exc)
            continue
        ranked.append((distance, idx, donor_id, donor_values.tolist()))

    ranked.sort(key=lambda r: r[0])

    if k >= len(ranked):
        return []
    distance, _idx, donor_id, values = ranked[k]
    return [{
        "donor_id": donor_id,
        "values": values,
        "distance": distance,
        "metric": "dtw",
    }]
