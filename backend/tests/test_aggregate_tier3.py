"""Tests for the OP-033 aggregate Tier-3 read-only summary-metric op."""
from __future__ import annotations

import copy

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.operations.tier3 import (
    METRIC_REGISTRY,
    DecomposedSegment,
    aggregate,
    register_metric,
)


RNG = np.random.default_rng(42)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _seg(seg_id: str, b: int, e: int, label: str = "trend",
         decomposition: DecompositionBlob | None = None) -> DecomposedSegment:
    return DecomposedSegment(
        segment_id=seg_id,
        start_index=b,
        end_index=e,
        label=label,
        decomposition=decomposition,
    )


def _stl_blob(period: int = 24, n: int = 120) -> DecompositionBlob:
    """Synthetic STL-style blob with a 'period' coefficient."""
    return DecompositionBlob(
        method="STL",
        components={
            "trend": np.zeros(n),
            "seasonal": np.zeros(n),
            "residual": np.zeros(n),
        },
        coefficients={"period": float(period)},
        residual=np.zeros(n),
        fit_metadata={"rmse": 0.0, "rank": 3, "n_params": 3,
                      "convergence": True, "version": "test"},
    )


def _eckhardt_blob(Q: np.ndarray, bfimax: float = 0.6) -> DecompositionBlob:
    baseflow = bfimax * Q
    quickflow = Q - baseflow
    return DecompositionBlob(
        method="Eckhardt",
        components={
            "baseflow": baseflow,
            "quickflow": quickflow,
            "residual": np.zeros_like(Q),
        },
        coefficients={"BFImax": bfimax, "a": 0.98},
        residual=np.zeros_like(Q),
        fit_metadata={"rmse": 0.0, "rank": 2, "n_params": 2,
                      "convergence": True, "version": "test"},
    )


def _gratsid_blob(tau: float = 30.0, n: int = 100) -> DecompositionBlob:
    return DecompositionBlob(
        method="GrAtSiD",
        components={"transient": np.zeros(n), "residual": np.zeros(n)},
        coefficients={"features": [{"type": "log", "tau": float(tau), "amplitude": 1.0}]},
        residual=np.zeros(n),
        fit_metadata={"rmse": 0.0, "rank": 1, "n_params": 1,
                      "convergence": True, "version": "test"},
    )


# ---------------------------------------------------------------------------
# Built-in metric coverage (one per metric)
# ---------------------------------------------------------------------------


def test_peak_returns_segment_max():
    X = np.array([1.0, 5.0, 3.0, 4.0, 2.0])
    seg = _seg("s1", 0, 4)
    result = aggregate(X, [seg], "peak")
    assert result == {"s1": 5.0}


def test_trough_returns_segment_min():
    X = np.array([1.0, -2.0, 3.0, 4.0])
    seg = _seg("s1", 0, 3)
    assert aggregate(X, [seg], "trough") == {"s1": -2.0}


def test_duration_includes_dt_factor():
    X = np.zeros(50)
    seg = _seg("s1", 0, 9)  # length = 10
    result = aggregate(X, [seg], "duration", aux={"dt": 0.5})
    assert result == {"s1": 5.0}


def test_duration_default_dt_is_one():
    X = np.zeros(50)
    seg = _seg("s1", 5, 14)  # length = 10
    assert aggregate(X, [seg], "duration") == {"s1": 10.0}


def test_area_uses_trapezoid_integral():
    X = np.array([0.0, 1.0, 2.0, 1.0, 0.0])
    seg = _seg("s1", 0, 4)
    result = aggregate(X, [seg], "area")
    expected = float(np.trapezoid(X, dx=1.0))
    assert result["s1"] == pytest.approx(expected)


def test_area_honors_dt_aux():
    X = np.ones(10)
    seg = _seg("s1", 0, 9)
    result = aggregate(X, [seg], "area", aux={"dt": 0.25})
    assert result["s1"] == pytest.approx(9 * 0.25)


def test_amplitude_returns_peak_minus_trough():
    X = np.array([1.0, 5.0, 3.0, 0.5, 2.0])
    seg = _seg("s1", 0, 4)
    assert aggregate(X, [seg], "amplitude") == {"s1": pytest.approx(4.5)}


def test_period_reads_from_decomposition_blob():
    X = np.zeros(120)
    blob = _stl_blob(period=24, n=120)
    seg = _seg("s1", 0, 119, label="cycle", decomposition=blob)
    assert aggregate(X, [seg], "period") == {"s1": 24.0}


def test_period_returns_none_without_decomposition():
    X = np.zeros(50)
    seg = _seg("s1", 0, 49, label="plateau", decomposition=None)
    assert aggregate(X, [seg], "period") == {"s1": None}


def test_tau_reads_first_gratsid_feature():
    X = np.zeros(100)
    blob = _gratsid_blob(tau=42.5, n=100)
    seg = _seg("s1", 0, 99, label="transient", decomposition=blob)
    assert aggregate(X, [seg], "tau") == {"s1": 42.5}


def test_tau_returns_none_for_non_gratsid_blob():
    X = np.zeros(120)
    blob = _stl_blob(period=24, n=120)  # STL, not GrAtSiD
    seg = _seg("s1", 0, 119, label="cycle", decomposition=blob)
    assert aggregate(X, [seg], "tau") == {"s1": None}


def test_tau_returns_none_when_features_empty():
    X = np.zeros(50)
    blob = DecompositionBlob(
        method="GrAtSiD",
        components={"transient": np.zeros(50), "residual": np.zeros(50)},
        coefficients={"features": []},
        residual=np.zeros(50),
        fit_metadata={"rmse": 0.0, "rank": 0, "n_params": 0,
                      "convergence": True, "version": "test"},
    )
    seg = _seg("s1", 0, 49, label="transient", decomposition=blob)
    assert aggregate(X, [seg], "tau") == {"s1": None}


def test_bfi_reads_baseflow_component_and_normalises():
    Q = np.array([10.0, 12.0, 8.0, 11.0])
    blob = _eckhardt_blob(Q, bfimax=0.6)
    seg = _seg("s1", 0, 3, label="plateau", decomposition=blob)
    result = aggregate(Q, [seg], "bfi")
    assert result["s1"] == pytest.approx(0.6, abs=1e-12)


def test_bfi_returns_none_when_no_baseflow_component():
    Q = np.array([1.0, 2.0, 3.0])
    blob = _stl_blob(period=4, n=3)  # STL has no baseflow
    seg = _seg("s1", 0, 2, label="cycle", decomposition=blob)
    assert aggregate(Q, [seg], "bfi") == {"s1": None}


def test_bfi_returns_none_when_total_flow_is_zero():
    Q = np.zeros(10)
    blob = _eckhardt_blob(Q, bfimax=0.6)
    seg = _seg("s1", 0, 9, label="plateau", decomposition=blob)
    assert aggregate(Q, [seg], "bfi") == {"s1": None}


def test_sos_eos_returns_indices_and_threshold():
    """Triangle waveform — SOS and EOS sit symmetrically around the peak."""
    X = np.array([0.0, 1.0, 2.0, 3.0, 2.0, 1.0, 0.0])
    seg = _seg("s1", 0, 6, label="trend")
    result = aggregate(X, [seg], "sos_eos", aux={"threshold_percent": 50.0})
    pair = result["s1"]
    assert isinstance(pair, dict)
    assert pair["sos"] == 2  # first sample at threshold 1.5: index 2 (value 2.0)
    assert pair["eos"] == 4  # last sample at threshold 1.5: index 4 (value 2.0)
    assert pair["threshold_value"] == pytest.approx(1.5)


def test_sos_eos_default_threshold_is_twenty_percent():
    X = np.linspace(0.0, 1.0, 11)  # amplitude = 1
    seg = _seg("s1", 0, 10, label="trend")
    result = aggregate(X, [seg], "sos_eos")
    pair = result["s1"]
    # threshold = 0.2 → first sample ≥ 0.2 is index 2 (value 0.2)
    assert pair["sos"] == 2
    assert pair["eos"] == 10  # rising-only signal: last sample is the EOS
    assert pair["threshold_value"] == pytest.approx(0.2)


def test_sos_eos_returns_none_for_flat_segment():
    X = np.full(20, 5.0)  # zero amplitude
    seg = _seg("s1", 0, 19, label="plateau")
    assert aggregate(X, [seg], "sos_eos") == {"s1": None}


def test_sos_eos_returns_none_for_single_sample():
    X = np.array([1.0, 2.0])
    seg = _seg("s1", 0, 0, label="plateau")  # length=1
    assert aggregate(X, [seg], "sos_eos") == {"s1": None}


def test_m0_computes_mu_times_area_times_slip():
    X = np.zeros(10)
    seg = _seg("s1", 0, 9, label="step")
    aux = {
        "shear_modulus": 3.0e10,  # Pa
        "fault_area": 1.0e6,      # m²
        "slip_from_segment": 1.0,  # m
    }
    result = aggregate(X, [seg], "m0", aux=aux)
    assert result["s1"] == pytest.approx(3.0e16)


def test_m0_returns_none_when_required_aux_missing():
    X = np.zeros(10)
    seg = _seg("s1", 0, 9, label="step")
    aux = {"shear_modulus": 3.0e10}  # missing area + slip
    assert aggregate(X, [seg], "m0", aux=aux) == {"s1": None}


# ---------------------------------------------------------------------------
# Multi-segment + result shape
# ---------------------------------------------------------------------------


def test_multi_segment_result_keyed_by_segment_id():
    X = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    segs = [_seg("a", 0, 1), _seg("b", 2, 3), _seg("c", 4, 5)]
    result = aggregate(X, segs, "peak")
    assert result == {"a": 2.0, "b": 4.0, "c": 6.0}


def test_empty_segment_list_returns_empty_dict():
    X = np.zeros(10)
    assert aggregate(X, [], "peak") == {}


def test_aggregate_only_slices_each_segment():
    """Per-segment metric must reflect only its own slice, not the full series."""
    X = np.array([1.0, 100.0, 100.0, 2.0])
    seg = _seg("s1", 0, 0)  # only X[0] = 1.0
    assert aggregate(X, [seg], "peak") == {"s1": 1.0}


# ---------------------------------------------------------------------------
# Read-only contract
# ---------------------------------------------------------------------------


def test_aggregate_does_not_mutate_input_series():
    X = np.array([1.0, 2.0, 3.0, 4.0])
    X_copy = X.copy()
    seg = _seg("s1", 0, 3)
    aggregate(X, [seg], "peak")
    np.testing.assert_array_equal(X, X_copy)


def test_aggregate_does_not_mutate_decomposition_blob():
    Q = np.array([10.0, 12.0, 8.0, 11.0])
    blob = _eckhardt_blob(Q, bfimax=0.6)
    blob_snapshot = copy.deepcopy(blob)
    seg = _seg("s1", 0, 3, label="plateau", decomposition=blob)
    aggregate(Q, [seg], "bfi")
    # Components, coefficients, fit_metadata, residual all unchanged.
    np.testing.assert_array_equal(blob.components["baseflow"], blob_snapshot.components["baseflow"])
    np.testing.assert_array_equal(blob.components["quickflow"], blob_snapshot.components["quickflow"])
    assert blob.coefficients == blob_snapshot.coefficients
    assert blob.fit_metadata == blob_snapshot.fit_metadata
    np.testing.assert_array_equal(blob.residual, blob_snapshot.residual)


def test_aggregate_does_not_mutate_segments_list():
    X = np.zeros(10)
    seg = _seg("s1", 0, 9)
    segs = [seg]
    aggregate(X, segs, "peak")
    assert segs == [seg]
    # Frozen dataclass: even if we tried, fields are immutable.
    assert seg.segment_id == "s1"
    assert seg.start_index == 0
    assert seg.end_index == 9


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_unknown_metric_raises_value_error():
    X = np.zeros(10)
    seg = _seg("s1", 0, 9)
    with pytest.raises(ValueError, match="unknown metric"):
        aggregate(X, [seg], "not_a_real_metric")


def test_negative_start_index_raises():
    X = np.zeros(10)
    seg = _seg("s1", -1, 5)
    with pytest.raises(ValueError, match="start_index"):
        aggregate(X, [seg], "peak")


def test_end_index_past_series_raises():
    X = np.zeros(10)
    seg = _seg("s1", 0, 10)
    with pytest.raises(ValueError, match="end_index"):
        aggregate(X, [seg], "peak")


def test_metric_runtime_failure_returns_none_without_crashing_table():
    """A metric that internally raises must not crash the whole table — it
    returns None for that segment so the UI table can still render."""

    @register_metric("__test_raising_metric__")
    def _explode(seg, X_seg, aux):
        raise RuntimeError("boom")

    try:
        X = np.zeros(10)
        seg = _seg("s1", 0, 9)
        result = aggregate(X, [seg], "__test_raising_metric__")
        assert result == {"s1": None}
    finally:
        del METRIC_REGISTRY["__test_raising_metric__"]


# ---------------------------------------------------------------------------
# Registry extensibility (domain packs add metrics)
# ---------------------------------------------------------------------------


def test_register_metric_decorator_adds_to_registry():
    @register_metric("__test_metric_temp__")
    def _metric(seg, X_seg, aux):
        return float(X_seg.sum())

    try:
        assert "__test_metric_temp__" in METRIC_REGISTRY
        X = np.array([1.0, 2.0, 3.0])
        seg = _seg("s1", 0, 2)
        assert aggregate(X, [seg], "__test_metric_temp__") == {"s1": 6.0}
    finally:
        del METRIC_REGISTRY["__test_metric_temp__"]


def test_register_metric_replacement_warns(caplog):
    """Re-registering a name with a different callable must warn."""

    @register_metric("__test_collide__")
    def _first(seg, X_seg, aux):
        return 1.0

    try:
        with caplog.at_level("WARNING"):
            @register_metric("__test_collide__")
            def _second(seg, X_seg, aux):
                return 2.0
        # Most-recent wins
        X = np.zeros(5)
        seg = _seg("s1", 0, 4)
        assert aggregate(X, [seg], "__test_collide__") == {"s1": 2.0}
        assert any("re-registering" in rec.message for rec in caplog.records)
    finally:
        del METRIC_REGISTRY["__test_collide__"]


def test_default_registry_contains_all_ten_built_in_metrics():
    expected = {
        "peak", "trough", "duration", "area", "amplitude",
        "period", "tau", "bfi", "sos_eos", "m0",
    }
    assert expected.issubset(set(METRIC_REGISTRY.keys()))


# ---------------------------------------------------------------------------
# None-result paths (metric not applicable)
# ---------------------------------------------------------------------------


def test_period_on_plateau_without_decomposition_is_none():
    X = np.zeros(50)
    seg = _seg("s1", 0, 49, label="plateau", decomposition=None)
    assert aggregate(X, [seg], "period") == {"s1": None}


def test_tau_on_cycle_segment_is_none():
    X = np.zeros(50)
    blob = _stl_blob(period=12, n=50)
    seg = _seg("s1", 0, 49, label="cycle", decomposition=blob)
    assert aggregate(X, [seg], "tau") == {"s1": None}


def test_bfi_on_trend_segment_is_none():
    X = np.linspace(0.1, 0.5, 30)
    seg = _seg("s1", 0, 29, label="trend", decomposition=None)
    assert aggregate(X, [seg], "bfi") == {"s1": None}


def test_period_blob_without_period_coefficient_is_none():
    """ETM-style blob (no 'period' key) — period metric reads None gracefully."""
    n = 50
    blob = DecompositionBlob(
        method="ETM",
        components={"x0": np.zeros(n), "linear_rate": np.zeros(n), "residual": np.zeros(n)},
        coefficients={"x0": 0.0, "linear_rate": 0.01},  # no 'period'
        residual=np.zeros(n),
        fit_metadata={"rmse": 0.0, "rank": 2, "n_params": 2,
                      "convergence": True, "version": "test"},
    )
    seg = _seg("s1", 0, n - 1, label="trend", decomposition=blob)
    assert aggregate(np.zeros(n), [seg], "period") == {"s1": None}


# ---------------------------------------------------------------------------
# Mixed-applicability fixture: integration smoke test
# ---------------------------------------------------------------------------


def test_mixed_segment_table_renders_per_segment_metric_or_none():
    """Three segments: cycle (has period), plateau (no period), trend (no
    period).  The aggregate table should show numeric value for cycle and
    None for the other two — exactly what UI-018 needs to render."""
    n = 200
    X = np.zeros(n)
    cycle_blob = _stl_blob(period=24, n=80)
    plateau_blob = _eckhardt_blob(np.full(60, 1.0), bfimax=0.6)

    segs = [
        _seg("c", 0, 79, label="cycle", decomposition=cycle_blob),
        _seg("p", 80, 139, label="plateau", decomposition=plateau_blob),
        _seg("t", 140, 199, label="trend", decomposition=None),
    ]
    result = aggregate(X, segs, "period")
    assert result == {"c": 24.0, "p": None, "t": None}
