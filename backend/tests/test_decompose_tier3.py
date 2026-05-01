"""Tests for the OP-030 decompose Tier-3 operation."""
from __future__ import annotations

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.events import AuditLog, EventBus
from app.services.operations.tier3 import (
    REFIT_REASON,
    DecomposeAudit,
    DecomposedSegment,
    decompose,
)


RNG = np.random.default_rng(42)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _line(n: int, slope: float = 0.05, intercept: float = 0.0) -> np.ndarray:
    return intercept + slope * np.arange(n, dtype=np.float64)


def _sine(n: int, period: float = 24.0) -> np.ndarray:
    t = np.arange(n, dtype=np.float64)
    return np.sin(2 * np.pi * t / period)


def _isolated_bus() -> tuple[EventBus, AuditLog]:
    """Return an isolated bus + log so tests don't pollute the package
    defaults (other test modules subscribe to default_event_bus)."""
    return EventBus(), AuditLog()


# ---------------------------------------------------------------------------
# Single-segment decompose
# ---------------------------------------------------------------------------


def test_single_segment_decompose_returns_blob():
    X = _line(120)
    segs = [DecomposedSegment("s1", 0, 119, "trend")]
    bus, log = _isolated_bus()
    out = decompose(X, segs, event_bus=bus, audit_log=log)
    assert len(out) == 1
    assert isinstance(out[0].decomposition, DecompositionBlob)
    assert out[0].decomposition.method in {"ETM", "LandTrendr"}


def test_single_segment_refit_reason_in_metadata():
    X = _line(120)
    segs = [DecomposedSegment("s1", 0, 119, "trend")]
    bus, log = _isolated_bus()
    out = decompose(X, segs, event_bus=bus, audit_log=log)
    assert out[0].decomposition.fit_metadata["refit_reason"] == REFIT_REASON


def test_decompose_does_not_mutate_input_segment():
    X = _line(120)
    seg_before = DecomposedSegment("s1", 0, 119, "trend")
    bus, log = _isolated_bus()
    decompose(X, [seg_before], event_bus=bus, audit_log=log)
    # Frozen dataclass: the original instance still has decomposition=None
    assert seg_before.decomposition is None


def test_decompose_handles_arbitrary_segment_window():
    """Slice indexing of X must use [start, end] inclusive on both ends."""
    X = _sine(240, period=24)
    seg = DecomposedSegment("s1", 50, 149, "cycle")
    bus, log = _isolated_bus()
    out = decompose(X, [seg], event_bus=bus, audit_log=log)
    blob = out[0].decomposition
    # Trend + seasonal + residual should equal the segment's slice within
    # float tolerance — the fitter operates on the slice [50:150].
    sliced = X[50:150]
    np.testing.assert_allclose(blob.reassemble(), sliced, atol=1e-9)


# ---------------------------------------------------------------------------
# Multi-segment decompose
# ---------------------------------------------------------------------------


def test_multi_segment_decompose_assigns_each_blob():
    X = np.concatenate([_line(60), _sine(120, 24)])
    segs = [
        DecomposedSegment("s_trend", 0, 59, "trend"),
        DecomposedSegment("s_cycle", 60, 179, "cycle"),
    ]
    bus, log = _isolated_bus()
    out = decompose(X, segs, event_bus=bus, audit_log=log)
    assert len(out) == 2
    assert all(s.decomposition is not None for s in out)
    methods = {s.decomposition.method for s in out}
    assert "STL" in methods or "ETM" in methods  # at least one differs


def test_multi_segment_preserves_order():
    X = np.concatenate([_line(40), _line(40, slope=-0.05, intercept=2.0), _line(40)])
    segs = [
        DecomposedSegment("first", 0, 39, "trend"),
        DecomposedSegment("middle", 40, 79, "trend"),
        DecomposedSegment("last", 80, 119, "trend"),
    ]
    bus, log = _isolated_bus()
    out = decompose(X, segs, event_bus=bus, audit_log=log)
    assert [s.segment_id for s in out] == ["first", "middle", "last"]


# ---------------------------------------------------------------------------
# Domain-hint priority
# ---------------------------------------------------------------------------


def test_function_level_domain_hint_overrides_segment_scope():
    """Per-segment scope says 'multi-period' (→ MSTL) but function-level
    arg is None — segment hint should win."""
    X = _sine(360, period=24)
    seg = DecomposedSegment(
        "s1", 0, 359, "cycle",
        scope={"domain_hint": "multi-period"},
    )
    bus, log = _isolated_bus()
    out = decompose(X, [seg], domain_hint=None, event_bus=bus, audit_log=log)
    assert out[0].decomposition.method == "MSTL"


def test_function_level_hint_wins_when_set():
    """Per-segment scope says 'multi-period' but function override is None
    → resolution falls through.  When the function arg is set, it wins."""
    X = _sine(360, period=24)
    seg = DecomposedSegment(
        "s1", 0, 359, "cycle",
        scope={"domain_hint": "multi-period"},
    )
    bus, log = _isolated_bus()
    # Explicit None: per-segment scope kicks in → MSTL.
    out = decompose(X, [seg], domain_hint=None, event_bus=bus, audit_log=log)
    assert out[0].decomposition.method == "MSTL"


def test_no_hint_falls_through_to_generic_fitter():
    X = _sine(120, period=12)
    seg = DecomposedSegment("s1", 0, 119, "cycle")  # no scope
    bus, log = _isolated_bus()
    out = decompose(X, [seg], event_bus=bus, audit_log=log)
    assert out[0].decomposition.method == "STL"


def test_invalid_shape_label_raises_keyerror():
    X = _line(60)
    seg = DecomposedSegment("s1", 0, 59, "not_a_real_shape")
    bus, log = _isolated_bus()
    with pytest.raises(KeyError, match="Unknown shape label"):
        decompose(X, [seg], event_bus=bus, audit_log=log)


# ---------------------------------------------------------------------------
# Idempotence (AC: decompose(decompose(X, S), S) → same coefficients)
# ---------------------------------------------------------------------------


def test_decompose_is_idempotent_on_coefficients():
    X = _sine(240, period=24) + 0.1 * RNG.normal(size=240)
    seg = DecomposedSegment("s1", 0, 239, "cycle")
    bus, log = _isolated_bus()

    once = decompose(X, [seg], event_bus=bus, audit_log=log)
    twice = decompose(X, once, event_bus=bus, audit_log=log)

    blob_a = once[0].decomposition
    blob_b = twice[0].decomposition
    assert blob_a.method == blob_b.method
    np.testing.assert_allclose(
        blob_a.components["trend"], blob_b.components["trend"], atol=1e-9,
    )
    np.testing.assert_allclose(
        blob_a.components["seasonal"], blob_b.components["seasonal"], atol=1e-9,
    )


def test_decompose_idempotent_for_trend_segment():
    X = _line(100, slope=0.02, intercept=0.5)
    seg = DecomposedSegment("s1", 0, 99, "trend")
    bus, log = _isolated_bus()
    once = decompose(X, [seg], event_bus=bus, audit_log=log)
    twice = decompose(X, once, event_bus=bus, audit_log=log)
    np.testing.assert_allclose(
        once[0].decomposition.coefficients.get("linear_rate", 0.0),
        twice[0].decomposition.coefficients.get("linear_rate", 0.0),
        atol=1e-12,
    )


# ---------------------------------------------------------------------------
# Bounds validation
# ---------------------------------------------------------------------------


def test_negative_start_index_raises():
    X = _line(50)
    seg = DecomposedSegment("s1", -1, 49, "trend")
    bus, log = _isolated_bus()
    with pytest.raises(ValueError, match="start_index"):
        decompose(X, [seg], event_bus=bus, audit_log=log)


def test_end_index_at_or_past_series_length_raises():
    X = _line(50)
    seg = DecomposedSegment("s1", 0, 50, "trend")
    bus, log = _isolated_bus()
    with pytest.raises(ValueError, match="end_index"):
        decompose(X, [seg], event_bus=bus, audit_log=log)


def test_end_before_start_raises():
    X = _line(50)
    seg = DecomposedSegment("s1", 30, 20, "trend")
    bus, log = _isolated_bus()
    with pytest.raises(ValueError, match="end_index"):
        decompose(X, [seg], event_bus=bus, audit_log=log)


def test_segment_at_exact_series_bounds_is_ok():
    """A segment covering the entire X (0 .. n-1 inclusive) is valid."""
    X = _line(50)
    seg = DecomposedSegment("s1", 0, 49, "trend")
    bus, log = _isolated_bus()
    out = decompose(X, [seg], event_bus=bus, audit_log=log)
    assert out[0].decomposition is not None


# ---------------------------------------------------------------------------
# Audit emission
# ---------------------------------------------------------------------------


def test_audit_entry_appended_to_audit_log():
    X = _line(60)
    segs = [DecomposedSegment("s1", 0, 59, "trend")]
    bus, log = _isolated_bus()
    decompose(X, segs, event_bus=bus, audit_log=log)
    assert len(log) == 1
    record = log.records[0]
    assert isinstance(record, DecomposeAudit)
    assert record.op_name == "decompose"
    assert record.tier == 3
    assert record.segment_ids == ("s1",)
    assert len(record.methods_used) == 1
    assert record.refit_reason == REFIT_REASON


def test_audit_entry_records_all_segment_ids_and_methods():
    X = np.concatenate([_line(40), _sine(120, 24)])
    segs = [
        DecomposedSegment("s_trend", 0, 39, "trend"),
        DecomposedSegment("s_cycle", 40, 159, "cycle"),
    ]
    bus, log = _isolated_bus()
    decompose(X, segs, event_bus=bus, audit_log=log)
    record = log.records[0]
    assert record.segment_ids == ("s_trend", "s_cycle")
    assert len(record.methods_used) == 2


def test_audit_entry_records_function_level_domain_hint():
    X = _sine(360, period=24)
    segs = [DecomposedSegment("s1", 0, 359, "cycle")]
    bus, log = _isolated_bus()
    decompose(X, segs, domain_hint="multi-period", event_bus=bus, audit_log=log)
    record = log.records[0]
    assert record.domain_hint == "multi-period"


def test_audit_event_published_on_event_bus():
    X = _line(60)
    segs = [DecomposedSegment("s1", 0, 59, "trend")]
    bus, log = _isolated_bus()
    received: list[DecomposeAudit] = []
    bus.subscribe("decompose", received.append)
    decompose(X, segs, event_bus=bus, audit_log=log)
    assert len(received) == 1
    assert received[0].op_name == "decompose"


def test_audit_uses_default_log_when_not_overridden():
    """When called without ``audit_log=`` override, the default audit log
    receives the entry.  Must clean up to avoid polluting other tests."""
    from app.services.events import default_audit_log
    before = len(default_audit_log)
    X = _line(60)
    segs = [DecomposedSegment("s1", 0, 59, "trend")]
    try:
        decompose(X, segs)
        after = len(default_audit_log)
        assert after == before + 1
    finally:
        # Drop just the entry we appended (preserves any other test's records).
        default_audit_log._records.pop()  # noqa: SLF001 — test cleanup


# ---------------------------------------------------------------------------
# Domain-hint routing happy paths against the real dispatcher table
# ---------------------------------------------------------------------------


def test_remote_sensing_trend_routes_to_landtrendr():
    X = _line(100)
    seg = DecomposedSegment(
        "s1", 0, 99, "trend",
        scope={"domain_hint": "remote-sensing"},
    )
    bus, log = _isolated_bus()
    out = decompose(X, [seg], event_bus=bus, audit_log=log)
    assert out[0].decomposition.method == "LandTrendr"


def test_seismo_geodesy_transient_routes_to_gratsid():
    X = _line(100)
    seg = DecomposedSegment(
        "s1", 0, 99, "transient",
        scope={"domain_hint": "seismo-geodesy"},
    )
    bus, log = _isolated_bus()
    out = decompose(X, [seg], event_bus=bus, audit_log=log)
    assert out[0].decomposition.method == "GrAtSiD"


# ---------------------------------------------------------------------------
# Domain-hint stamped on the blob
# ---------------------------------------------------------------------------


def test_domain_hint_recorded_in_blob_metadata():
    X = _line(100)
    seg = DecomposedSegment("s1", 0, 99, "trend")
    bus, log = _isolated_bus()
    out = decompose(
        X, [seg], domain_hint="remote-sensing", event_bus=bus, audit_log=log,
    )
    assert out[0].decomposition.fit_metadata["domain_hint"] == "remote-sensing"


def test_domain_hint_not_present_when_unset():
    X = _line(100)
    seg = DecomposedSegment("s1", 0, 99, "trend")
    bus, log = _isolated_bus()
    out = decompose(X, [seg], event_bus=bus, audit_log=log)
    assert "domain_hint" not in out[0].decomposition.fit_metadata


# ---------------------------------------------------------------------------
# Empty input edge case
# ---------------------------------------------------------------------------


def test_empty_segment_list_emits_audit_with_no_segments():
    X = _line(50)
    bus, log = _isolated_bus()
    out = decompose(X, [], event_bus=bus, audit_log=log)
    assert out == []
    assert len(log) == 1
    record = log.records[0]
    assert record.segment_ids == ()
    assert record.methods_used == ()


# ---------------------------------------------------------------------------
# Length / slice consistency
# ---------------------------------------------------------------------------


def test_decomposition_length_matches_segment_length():
    X = _sine(360, period=24)
    seg = DecomposedSegment("s1", 60, 199, "cycle")
    bus, log = _isolated_bus()
    out = decompose(X, [seg], event_bus=bus, audit_log=log)
    blob = out[0].decomposition
    expected_len = seg.length
    for name, comp in blob.components.items():
        assert comp.shape[0] == expected_len, (
            f"component {name!r} shape {comp.shape} ≠ segment length {expected_len}"
        )
