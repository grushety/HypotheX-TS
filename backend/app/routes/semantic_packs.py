"""Semantic-pack HTTP surface (UI-014).

Three thin routes:

- ``GET  /api/semantic-packs``                 — list the built-in packs and
                                                 their labels (read from YAML).
- ``POST /api/semantic-packs/label-segments``  — run the active pack's
                                                 detectors over a list of
                                                 segments, return one label
                                                 per segment.
- ``POST /api/semantic-packs/validate-yaml``   — parse + load-pack a custom
                                                 YAML body without persisting
                                                 it; surface line-numbered
                                                 errors back to the UI.

The heavy lifting (registry, predicate eval, label matching) lives in
``app.services.semantic_packs``; routes only adapt JSON to that API.
"""
from __future__ import annotations

import functools
import pathlib
import tempfile
from typing import Any

import numpy as np
import yaml
from flask import Blueprint, jsonify, request

from app.services.semantic_packs import (
    SemanticPack,
    label_segment,
    load_pack,
    validate_predicate_strict,
)

semantic_packs_bp = Blueprint("semantic_packs", __name__)

BUILT_IN_PACK_NAMES: tuple[str, ...] = ("hydrology", "seismo_geodesy", "remote_sensing")

# Cap uploaded YAML at 64 KiB. A semantic-pack file is a small set of label
# definitions; anything substantially larger is either an attempt to wedge
# the temp-dir loader or a user mistake.
MAX_CUSTOM_YAML_BYTES: int = 64 * 1024


def _harden_uploaded_pack(pack: SemanticPack) -> None:
    """Validate every predicate in an uploaded pack against the strict
    AST whitelist (disallows ``**``).

    The semantic-pack predicate evaluator at
    `services/semantic_packs/core.py:185` documents that ``ast.Pow`` must
    be dropped once the trust boundary widens to user-uploaded packs.
    UI-014 is exactly that boundary widening — we therefore re-validate
    every predicate with `validate_predicate_strict` before any detector
    runs.

    Raises :class:`ValueError` if any predicate is disallowed.
    """
    for label in pack.semantic_labels.values():
        validate_predicate_strict(label.context_predicate)


def _serialize_pack(pack: SemanticPack) -> dict[str, Any]:
    return {
        "name": pack.name,
        "version": pack.version,
        "labels": [
            {
                "name": label.name,
                "shape_primitive": label.shape_primitive,
                "detector": label.detector_name,
                "context_predicate": label.context_predicate,
            }
            for label in pack.semantic_labels.values()
        ],
    }


@functools.lru_cache(maxsize=8)
def _load_built_in_pack(name: str) -> SemanticPack:
    """Load and cache a built-in pack. Pack YAML files ship with the codebase
    and don't change between requests — cache to avoid re-parsing on every
    `GET /api/semantic-packs` call."""
    return load_pack(name)


def _load_custom_pack(yaml_text: str) -> SemanticPack:
    """Materialise a SemanticPack from a YAML body without persisting it.

    Uses a TemporaryDirectory so the existing path-based `load_pack` can be
    reused unchanged. The temp directory is removed before returning.

    All predicates are re-validated against the strict whitelist before
    return — see :func:`_harden_uploaded_pack`.
    """
    if len(yaml_text.encode("utf-8")) > MAX_CUSTOM_YAML_BYTES:
        raise ValueError(
            f"Uploaded YAML exceeds {MAX_CUSTOM_YAML_BYTES} bytes; "
            "semantic packs are expected to be a few hundred bytes per label."
        )
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = pathlib.Path(tmpdir) / "custom.yaml"
        tmp_path.write_text(yaml_text, encoding="utf-8")
        pack = load_pack("custom", pack_dir=pathlib.Path(tmpdir))
    _harden_uploaded_pack(pack)
    return pack


@semantic_packs_bp.get("/api/semantic-packs")
def list_semantic_packs():
    payload: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    for name in BUILT_IN_PACK_NAMES:
        try:
            payload.append(_serialize_pack(_load_built_in_pack(name)))
        except (FileNotFoundError, ValueError) as exc:
            errors[name] = str(exc)
    return jsonify({"packs": payload, "errors": errors})


@semantic_packs_bp.post("/api/semantic-packs/label-segments")
def label_segments_route():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    pack_name = body.get("pack_name")
    custom_yaml = body.get("custom_yaml")
    if not pack_name and not custom_yaml:
        return jsonify({"error": "Either pack_name or custom_yaml is required."}), 400

    try:
        pack = (
            _load_custom_pack(str(custom_yaml))
            if custom_yaml
            else _load_built_in_pack(str(pack_name))
        )
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    raw_values = body.get("values", [])
    if not isinstance(raw_values, list):
        return jsonify({"error": "values must be an array of numbers."}), 400
    try:
        values = np.asarray(raw_values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"values must be numeric: {exc}"}), 400

    raw_segments = body.get("segments", [])
    if not isinstance(raw_segments, list):
        return jsonify({"error": "segments must be an array of objects."}), 400

    context_template = body.get("context") or {}
    if not isinstance(context_template, dict):
        return jsonify({"error": "context must be a JSON object."}), 400

    results: list[dict[str, Any]] = []
    for seg in raw_segments:
        if not isinstance(seg, dict):
            return jsonify({"error": "Each segment entry must be an object."}), 400
        seg_id = seg.get("id")
        start = seg.get("start")
        end = seg.get("end")
        shape = seg.get("shape")
        if not isinstance(seg_id, str) or not isinstance(shape, str):
            return jsonify({"error": "segment.id and segment.shape are required."}), 400
        if not isinstance(start, int) or not isinstance(end, int):
            return jsonify({"error": "segment.start and segment.end must be integers."}), 400
        if start < 0 or end >= len(values) or end < start:
            results.append({"segment_id": seg_id, "label": None, "confidence": 0.0})
            continue

        x_seg = values[start : end + 1]
        ctx = dict(context_template)
        if "dt" not in ctx:
            ctx["dt"] = 1.0
        matches = label_segment(pack, x_seg, shape, ctx)
        if matches:
            label_name, confidence = matches[0]
            results.append(
                {
                    "segment_id": seg_id,
                    "label": label_name,
                    "confidence": float(confidence),
                }
            )
        else:
            results.append({"segment_id": seg_id, "label": None, "confidence": 0.0})

    return jsonify({"pack_name": pack.name, "results": results})


@semantic_packs_bp.post("/api/semantic-packs/validate-yaml")
def validate_yaml_route():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or "yaml" not in body:
        return jsonify({"error": "Request body must include a 'yaml' string."}), 400

    yaml_text = body.get("yaml")
    if not isinstance(yaml_text, str):
        return jsonify({"error": "'yaml' must be a string."}), 400

    try:
        pack = _load_custom_pack(yaml_text)
    except yaml.YAMLError as exc:
        line = None
        if hasattr(exc, "problem_mark") and exc.problem_mark is not None:
            line = int(exc.problem_mark.line) + 1
        return jsonify(
            {"ok": False, "error": {"message": str(exc), "line": line, "kind": "yaml"}}
        )
    except ValueError as exc:
        return jsonify(
            {"ok": False, "error": {"message": str(exc), "line": None, "kind": "schema"}}
        )

    return jsonify({"ok": True, "pack": _serialize_pack(pack)})
