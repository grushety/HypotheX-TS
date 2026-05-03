"""Route tests for ``POST /api/operations/invoke`` (HTS-100).

Covers:
- Happy path per tier (1, 2, 3 mutating, 3 read-only aggregate).
- Error responses (400 unknown tier, 400 unknown op, 404 unknown segment,
  400 malformed params).
- Audit_id round-trips through ``default_audit_log``.
- Label chip published to ``default_event_bus`` for Tier 1 / Tier 2.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.services.events import default_audit_log, default_event_bus
from app.services.operations.relabeler.label_chip import LabelChip


def _segments(label: str = "trend") -> list[dict]:
    return [{"id": "s0", "start": 0, "end": 49, "label": label}]


def _values(n: int = 50, seed: int = 0) -> list[float]:
    rng = np.random.default_rng(seed)
    base = np.linspace(0.0, 5.0, n) + rng.normal(0.0, 0.05, size=n)
    return base.tolist()


@pytest.fixture(autouse=True)
def _reset_audit_state():
    default_audit_log.clear()
    yield
    default_audit_log.clear()


# ---------------------------------------------------------------------------
# Happy paths — one per tier
# ---------------------------------------------------------------------------


def test_tier1_happy_path_offset(client):
    payload = {
        "series_id": "S",
        "segment_id": "s0",
        "tier": 1,
        "op_name": "offset",
        "params": {"delta": 2.0},
        "domain_hint": None,
        "sample_values": _values(),
        "segments": _segments(),
        "compensation_mode": None,
        "target_class": None,
    }
    rv = client.post("/api/operations/invoke", json=payload)
    assert rv.status_code == 200, rv.get_json()
    body = rv.get_json()
    assert body["op_name"] == "offset"
    assert body["tier"] == 1
    assert body["edit_space"] == "signal"
    assert body["values"] is not None
    # offset adds 2.0 to every sample in the segment slice
    expected = [v + 2.0 for v in payload["sample_values"][:50]]
    np.testing.assert_allclose(body["values"], expected, atol=1e-9)
    assert body["label_chip"] is not None
    assert body["label_chip"]["tier"] == 1
    assert body["audit_id"] == 0


def test_tier2_happy_path_change_slope(client):
    payload = {
        "series_id": "S",
        "segment_id": "s0",
        "tier": 2,
        "op_name": "trend_change_slope",
        "params": {"alpha": 0.5},
        "domain_hint": None,
        "sample_values": _values(),
        "segments": _segments(label="trend"),
        "compensation_mode": "naive",
        "target_class": None,
    }
    rv = client.post("/api/operations/invoke", json=payload)
    assert rv.status_code == 200, rv.get_json()
    body = rv.get_json()
    assert body["tier"] == 2
    assert body["edit_space"] == "coefficient"
    assert body["values"] is not None
    assert len(body["values"]) == 50
    assert body["label_chip"] is not None
    assert body["label_chip"]["tier"] == 2
    assert body["audit_id"] is not None


def test_tier2_raw_signal_path_spike_remove(client):
    """spike.remove takes X_seg directly (not a blob); covers the raw-signal Tier-2 branch."""
    n = 50
    rng = np.random.default_rng(0)
    series = rng.normal(0.0, 0.2, size=n)
    series[25] = 8.0  # spike
    payload = {
        "series_id": "S",
        "segment_id": "s0",
        "tier": 2,
        "op_name": "spike_remove",
        "params": {"method": "hampel"},
        "domain_hint": None,
        "sample_values": series.tolist(),
        "segments": [{"id": "s0", "start": 0, "end": n - 1, "label": "spike"}],
        "compensation_mode": None,
        "target_class": None,
    }
    rv = client.post("/api/operations/invoke", json=payload)
    assert rv.status_code == 200, rv.get_json()
    body = rv.get_json()
    assert body["op_name"] == "remove"
    assert body["tier"] == 2
    assert body["edit_space"] == "signal"
    assert body["label_chip"]["tier"] == 2


def test_tier3_enforce_conservation_happy_path(client):
    n = 12
    P = [1.0] * n
    ET = [0.3] * n
    Q = [0.2] * n
    dS = [0.4] * n  # residual = 1 − 0.3 − 0.2 − 0.4 = 0.1 ≠ 0; project corrects it
    payload = {
        "series_id": "S",
        "segment_id": "s0",
        "tier": 3,
        "op_name": "enforce_conservation",
        "params": {
            "X_all": {"P": P, "ET": ET, "Q": Q, "dS": dS},
            "law": "water_balance",
        },
        "sample_values": P,
        "segments": [{"id": "s0", "start": 0, "end": n - 1, "label": "trend"}],
        "compensation_mode": "local",
    }
    rv = client.post("/api/operations/invoke", json=payload)
    assert rv.status_code == 200, rv.get_json()
    body = rv.get_json()
    assert body["op_name"] == "enforce_conservation"
    assert body["constraint_residual"]["law"] == "water_balance"
    assert body["constraint_residual"]["converged"] is True
    assert body["audit_id"] is not None


def test_tier3_decompose_happy_path(client):
    payload = {
        "series_id": "S",
        "segment_id": "s0",
        "tier": 3,
        "op_name": "decompose",
        "params": {},
        "domain_hint": None,
        "sample_values": _values(),
        "segments": _segments(label="trend"),
        "compensation_mode": None,
        "target_class": None,
    }
    rv = client.post("/api/operations/invoke", json=payload)
    assert rv.status_code == 200, rv.get_json()
    body = rv.get_json()
    assert body["op_name"] == "decompose"
    assert body["tier"] == 3
    assert body["edit_space"] == "coefficient"
    assert body["audit_id"] is not None
    # Tier-3 decompose emits a DecomposeAudit, not a LabelChip
    assert body["label_chip"] is None


def test_tier3_aggregate_read_only(client):
    payload = {
        "series_id": "S",
        "segment_id": "s0",
        "tier": 3,
        "op_name": "aggregate",
        "params": {"metric": "peak"},
        "domain_hint": None,
        "sample_values": _values(),
        "segments": _segments(label="trend"),
        "compensation_mode": None,
        "target_class": None,
    }
    rv = client.post("/api/operations/invoke", json=payload)
    assert rv.status_code == 200, rv.get_json()
    body = rv.get_json()
    assert body["op_name"] == "aggregate"
    assert body["values"] is None
    assert body["label_chip"] is None
    assert body["audit_id"] is None  # read-only: no audit appended
    assert body["aggregate_result"] is not None
    assert "s0" in body["aggregate_result"]


# ---------------------------------------------------------------------------
# Error responses
# ---------------------------------------------------------------------------


def test_unknown_tier_400(client):
    payload = {
        "series_id": "S",
        "segment_id": "s0",
        "tier": 7,
        "op_name": "scale",
        "sample_values": _values(),
        "segments": _segments(),
    }
    rv = client.post("/api/operations/invoke", json=payload)
    assert rv.status_code == 400
    assert "tier" in rv.get_json()["error"].lower()


def test_unknown_op_400(client):
    payload = {
        "series_id": "S",
        "segment_id": "s0",
        "tier": 1,
        "op_name": "warp_to_doom",
        "sample_values": _values(),
        "segments": _segments(),
    }
    rv = client.post("/api/operations/invoke", json=payload)
    assert rv.status_code == 400
    assert "warp_to_doom" in rv.get_json()["error"]


def test_unknown_segment_404(client):
    payload = {
        "series_id": "S",
        "segment_id": "missing-seg",
        "tier": 1,
        "op_name": "offset",
        "params": {"delta": 1.0},
        "sample_values": _values(),
        "segments": _segments(),
    }
    rv = client.post("/api/operations/invoke", json=payload)
    assert rv.status_code == 404
    assert "missing-seg" in rv.get_json()["error"]


def test_malformed_params_400(client):
    # offset() requires 'delta' (positional), so omitting it is a TypeError
    payload = {
        "series_id": "S",
        "segment_id": "s0",
        "tier": 1,
        "op_name": "offset",
        "params": {},
        "sample_values": _values(),
        "segments": _segments(),
    }
    rv = client.post("/api/operations/invoke", json=payload)
    assert rv.status_code == 400
    assert "delta" in rv.get_json()["error"].lower()


# ---------------------------------------------------------------------------
# Audit / event-bus contract
# ---------------------------------------------------------------------------


def test_audit_id_round_trips_through_audit_log(client):
    pre_len = len(default_audit_log)
    payload = {
        "series_id": "S",
        "segment_id": "s0",
        "tier": 1,
        "op_name": "offset",
        "params": {"delta": 1.0},
        "sample_values": _values(),
        "segments": _segments(),
    }
    rv = client.post("/api/operations/invoke", json=payload)
    assert rv.status_code == 200
    body = rv.get_json()
    audit_id = body["audit_id"]
    assert audit_id == pre_len
    assert len(default_audit_log) == pre_len + 1
    # The recorded chip is at index audit_id and matches the response
    record = default_audit_log.records[audit_id]
    assert isinstance(record, LabelChip)
    assert record.chip_id == body["label_chip"]["chip_id"]


def test_label_chip_published_to_event_bus(client):
    captured: list = []

    def _capture(chip):
        captured.append(chip)

    default_event_bus.subscribe("label_chip", _capture)
    try:
        payload = {
            "series_id": "S",
            "segment_id": "s0",
            "tier": 1,
            "op_name": "offset",
            "params": {"delta": 1.0},
            "sample_values": _values(),
            "segments": _segments(),
        }
        rv = client.post("/api/operations/invoke", json=payload)
        assert rv.status_code == 200
    finally:
        default_event_bus.unsubscribe("label_chip", _capture)

    assert len(captured) == 1
    assert isinstance(captured[0], LabelChip)
    assert captured[0].tier == 1
    assert captured[0].op_name == "offset"
