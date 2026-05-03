"""Route tests for ``POST /api/segments/<id>/scope`` (HTS-106)."""
from __future__ import annotations

import pytest

from app.routes.segments import ScopeStore, ScopeUpdateAudit
from app.services.events import default_audit_log


@pytest.fixture(autouse=True)
def _reset_audit_log():
    default_audit_log.clear()
    yield
    default_audit_log.clear()


def _base_scope(**overrides):
    scope = {
        "window_size": 30,
        "mode": "sliding",
        "reference": None,
        "domain_hint": "hydrology",
    }
    scope.update(overrides)
    return scope


def _payload(**overrides):
    body = {
        "scope": _base_scope(),
        "previousScope": None,
        "triggerReclassify": True,
    }
    body.update(overrides)
    return body


def test_scope_update_happy_path(client):
    rv = client.post(
        "/api/segments/seg-001/scope",
        json=_payload(),
    )
    assert rv.status_code == 200, rv.get_json()
    body = rv.get_json()
    assert body["segment_id"] == "seg-001"
    assert body["scope"]["window_size"] == 30
    assert body["scope"]["mode"] == "sliding"
    assert isinstance(body["audit_id"], str) and body["audit_id"]
    assert body["trigger_reclassify"] is True
    # Audit was appended
    assert len(default_audit_log) == 1
    record = default_audit_log.records[-1]
    assert isinstance(record, ScopeUpdateAudit)
    assert record.segment_id == "seg-001"
    assert record.next_scope["window_size"] == 30
    assert record.previous_scope is None


def test_scope_update_records_previous_scope(client):
    client.post("/api/segments/seg-002/scope", json=_payload())
    rv = client.post(
        "/api/segments/seg-002/scope",
        json=_payload(scope=_base_scope(window_size=42, mode="fixed", reference="2024-01-01T00:00:00")),
    )
    assert rv.status_code == 200
    record = default_audit_log.records[-1]
    assert record.previous_scope["window_size"] == 30
    assert record.next_scope["window_size"] == 42
    assert record.next_scope["mode"] == "fixed"


@pytest.mark.parametrize("bad_scope, expected_msg", [
    ({}, "scope.window_size is required."),
    ({"window_size": 0, "mode": "sliding"}, "scope.window_size must be >= 1."),
    ({"window_size": "five", "mode": "sliding"}, "scope.window_size must be an integer."),
    ({"window_size": 10, "mode": "exotic"}, "scope.mode must be one of"),
    ({"window_size": 10, "mode": "fixed"}, "scope.reference is required"),
    ({"window_size": 10, "mode": "sliding", "domain_hint": 17}, "scope.domain_hint must be a string"),
])
def test_scope_update_malformed_returns_400(client, bad_scope, expected_msg):
    rv = client.post(
        "/api/segments/seg-bad/scope",
        json={"scope": bad_scope},
    )
    assert rv.status_code == 400
    assert expected_msg in rv.get_json()["error"]


def test_scope_update_unknown_segment_returns_404_when_required(app):
    # The route is permissive by default (segments don't have to be
    # pre-registered); flipping SCOPE_REQUIRE_KNOWN_SEGMENT enforces
    # the 404 path for callers that want it (e.g. once segment state
    # is fully managed server-side).
    store = ScopeStore()
    store.register("seg-known")
    app.config["SCOPE_STORE"] = store
    app.config["SCOPE_REQUIRE_KNOWN_SEGMENT"] = True
    rv = app.test_client().post(
        "/api/segments/seg-unknown/scope",
        json=_payload(),
    )
    assert rv.status_code == 404
    assert "seg-unknown" in rv.get_json()["error"]


def test_scope_update_non_object_body_returns_400(client):
    rv = client.post(
        "/api/segments/seg-001/scope",
        data="not json",
        headers={"Content-Type": "application/json"},
    )
    assert rv.status_code == 400
