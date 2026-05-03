"""Segment-mutation routes (HTS-106).

Single endpoint today: ``POST /api/segments/<segment_id>/scope``. Persists
the scope dict on an in-process session-scoped store and emits a
``scope_updated`` audit event to ``default_audit_log`` so downstream
consumers (audit panel, OP-040 reclassifier) can react.

The store lives on ``app.config['SCOPE_STORE']`` so tests can inject a
fresh instance per request and so the ScopeStore can be cleared between
sessions. There is no DB table for segment state today (segments are
re-derived from the dataset each load); this store is the
prototype-level seam where per-session scope edits accumulate. A future
ticket can promote it into a real persistence layer once the use-case
hardens.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from app.services.events import default_audit_log

logger = logging.getLogger(__name__)

segments_bp = Blueprint("segments", __name__)


_ALLOWED_SCOPE_MODES = frozenset({"fixed", "sliding"})


@dataclass
class ScopeUpdateAudit:
    """Audit record emitted when a segment scope is updated.

    Mirrors the shape of the OP-030 / OP-032 audit records (op_name +
    tier + segment_ids) so downstream consumers can treat all audits
    uniformly.
    """

    op_name: str
    tier: int
    segment_id: str
    previous_scope: dict[str, Any] | None
    next_scope: dict[str, Any]
    trigger_reclassify: bool
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class ScopeStore:
    """In-process per-session scope dictionary keyed by segment_id."""

    def __init__(self) -> None:
        self._scopes: dict[str, dict[str, Any]] = {}
        self._known_segments: set[str] = set()

    def register(self, segment_id: str) -> None:
        self._known_segments.add(segment_id)

    def has(self, segment_id: str) -> bool:
        return segment_id in self._known_segments or segment_id in self._scopes

    def get(self, segment_id: str) -> dict[str, Any] | None:
        return self._scopes.get(segment_id)

    def set(self, segment_id: str, scope: dict[str, Any]) -> dict[str, Any] | None:
        previous = self._scopes.get(segment_id)
        self._scopes[segment_id] = dict(scope)
        self._known_segments.add(segment_id)
        return previous

    def clear(self) -> None:
        self._scopes.clear()
        self._known_segments.clear()


def _get_scope_store() -> ScopeStore:
    store = current_app.config.get("SCOPE_STORE")
    if store is None:
        store = ScopeStore()
        current_app.config["SCOPE_STORE"] = store
    return store


def _validate_scope(scope: Any) -> dict[str, Any] | str:
    """Return a normalised scope dict on success; an error string on failure."""
    if not isinstance(scope, dict):
        return "scope must be an object."
    window_size = scope.get("window_size")
    mode = scope.get("mode")
    reference = scope.get("reference")
    domain_hint = scope.get("domain_hint")

    if window_size is None:
        return "scope.window_size is required."
    try:
        window_size_int = int(window_size)
    except (TypeError, ValueError):
        return "scope.window_size must be an integer."
    if window_size_int < 1:
        return "scope.window_size must be >= 1."

    if mode not in _ALLOWED_SCOPE_MODES:
        return f"scope.mode must be one of {sorted(_ALLOWED_SCOPE_MODES)}."

    if mode == "fixed" and reference is None:
        return "scope.reference is required when mode='fixed'."

    if domain_hint is not None and not isinstance(domain_hint, str):
        return "scope.domain_hint must be a string or null."

    return {
        "window_size": window_size_int,
        "mode": mode,
        "reference": reference,
        "domain_hint": domain_hint,
    }


@segments_bp.post("/api/segments/<segment_id>/scope")
def update_segment_scope(segment_id: str):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    scope_or_error = _validate_scope(payload.get("scope"))
    if isinstance(scope_or_error, str):
        return jsonify({"error": scope_or_error}), 400
    scope = scope_or_error

    trigger_reclassify = bool(payload.get("triggerReclassify", False))

    store = _get_scope_store()

    require_known = current_app.config.get("SCOPE_REQUIRE_KNOWN_SEGMENT", False)
    if require_known and not store.has(segment_id):
        return jsonify({"error": f"Unknown segment {segment_id!r}."}), 404

    previous_scope = store.set(segment_id, scope)

    audit = ScopeUpdateAudit(
        op_name="scope_updated",
        tier=0,
        segment_id=segment_id,
        previous_scope=previous_scope,
        next_scope=scope,
        trigger_reclassify=trigger_reclassify,
    )
    default_audit_log.append(audit)

    return jsonify({
        "segment_id": segment_id,
        "scope": scope,
        "audit_id": audit.audit_id,
        "trigger_reclassify": trigger_reclassify,
    }), 200
