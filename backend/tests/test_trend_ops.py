"""Tests for Tier-2 trend ops: flatten, reverse_direction, change_slope,
linearise, extrapolate, add_acceleration (OP-021).
"""

import math

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.operations.tier2.trend import (
    add_acceleration,
    change_slope,
    extrapolate,
    flatten,
    linearise,
    reverse_direction,
)
from app.services.operations.tier2.plateau import Tier2OpResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _etm_blob(n: int = 20, x0: float = 2.0, rate: float = 0.5) -> DecompositionBlob:
    """Synthetic ETM blob: x(t) = x0 + rate * t_centered."""
    t = np.arange(n, dtype=np.float64)
    return DecompositionBlob(
        method="ETM",
        components={
            "x0": np.full(n, x0, dtype=np.float64),
            "linear_rate": rate * t,
            "residual": np.zeros(n, dtype=np.float64),
        },
        coefficients={"x0": x0, "linear_rate": rate},
        residual=np.zeros(n, dtype=np.float64),
        fit_metadata={"rmse": 0.0, "rank": 2, "n_params": 2, "convergence": True},
    )


def _lt_blob(n: int = 20) -> DecompositionBlob:
    """Synthetic LandTrendr blob: two-segment piecewise linear."""
    t = np.arange(n, dtype=np.float64)
    brk = n // 2
    s1, i1 = 0.3, 1.0
    s2, i2 = -0.2, 5.0
    trend = np.empty(n, dtype=np.float64)
    trend[:brk] = i1 + s1 * t[:brk]
    trend[brk:] = i2 + s2 * t[brk:]
    residual = np.zeros(n, dtype=np.float64)
    return DecompositionBlob(
        method="LandTrendr",
        components={"trend": trend, "residual": residual},
        coefficients={
            "breakpoint": brk,
            "slope_1": s1, "intercept_1": i1,
            "slope_2": s2, "intercept_2": i2,
        },
        residual=residual,
        fit_metadata={"rmse": 0.0, "rank": 2, "n_params": 4, "convergence": True},
    )


def _t(n: int = 20) -> np.ndarray:
    return np.arange(n, dtype=np.float64)


# ---------------------------------------------------------------------------
# flatten — ETM
# ---------------------------------------------------------------------------


def test_flatten_etm_returns_tier2_result():
    result = flatten(_etm_blob(), t=_t())
    assert isinstance(result, Tier2OpResult)


def test_flatten_etm_zeroes_slope():
    blob = _etm_blob(x0=3.0, rate=0.5)
    result = flatten(blob, t=_t())
    assert np.allclose(result.values, 3.0, atol=1e-12)


def test_flatten_etm_relabel_deterministic_plateau():
    result = flatten(_etm_blob(), t=_t())
    assert result.relabel.rule_class == "DETERMINISTIC"
    assert result.relabel.new_shape == "plateau"
    assert result.relabel.needs_resegment is False


def test_flatten_etm_op_name():
    result = flatten(_etm_blob(), t=_t())
    assert result.op_name == "change_slope"


def test_flatten_does_not_mutate_caller_blob():
    blob = _etm_blob(rate=0.5)
    flatten(blob, t=_t())
    assert math.isclose(blob.coefficients["linear_rate"], 0.5, abs_tol=1e-12)


# ---------------------------------------------------------------------------
# flatten — LandTrendr
# ---------------------------------------------------------------------------


def test_flatten_lt_returns_constant_signal():
    blob = _lt_blob()
    t = _t()
    result = flatten(blob, t=t)
    assert np.allclose(result.values, result.values[0], atol=1e-12)


def test_flatten_lt_does_not_mutate_caller_blob():
    blob = _lt_blob()
    original_s1 = blob.coefficients["slope_1"]
    flatten(blob, t=_t())
    assert math.isclose(blob.coefficients["slope_1"], original_s1, abs_tol=1e-12)


# ---------------------------------------------------------------------------
# flatten == change_slope(alpha=0) identity
# ---------------------------------------------------------------------------


def test_flatten_and_change_slope_zero_identical_etm():
    blob = _etm_blob(x0=1.0, rate=0.7)
    r_flatten = flatten(blob, t=_t())
    r_change = change_slope(blob, alpha=0.0, t=_t())
    assert np.allclose(r_flatten.values, r_change.values, atol=1e-12)


def test_flatten_and_change_slope_zero_identical_lt():
    blob = _lt_blob()
    r_flatten = flatten(blob, t=_t())
    r_change = change_slope(blob, alpha=0.0, t=_t())
    assert np.allclose(r_flatten.values, r_change.values, atol=1e-12)


# ---------------------------------------------------------------------------
# change_slope — ETM
# ---------------------------------------------------------------------------


def test_change_slope_etm_halves_rate():
    n = 10
    blob = _etm_blob(n=n, x0=0.0, rate=1.0)
    t = _t(n)
    result = change_slope(blob, alpha=0.5, t=t)
    expected = 0.0 + 0.5 * t
    assert np.allclose(result.values, expected, atol=1e-12)


def test_change_slope_etm_doubles_rate():
    n = 10
    blob = _etm_blob(n=n, x0=0.0, rate=1.0)
    t = _t(n)
    result = change_slope(blob, alpha=2.0, t=t)
    expected = 2.0 * t
    assert np.allclose(result.values, expected, atol=1e-12)


def test_change_slope_etm_preserved_relabel():
    result = change_slope(_etm_blob(), alpha=0.5, t=_t())
    assert result.relabel.rule_class == "PRESERVED"
    assert result.relabel.new_shape == "trend"


def test_change_slope_etm_zero_deterministic_relabel():
    result = change_slope(_etm_blob(), alpha=0.0, t=_t())
    assert result.relabel.rule_class == "DETERMINISTIC"
    assert result.relabel.new_shape == "plateau"


def test_change_slope_does_not_mutate_blob():
    blob = _etm_blob(rate=1.0)
    change_slope(blob, alpha=2.0, t=_t())
    assert math.isclose(blob.coefficients["linear_rate"], 1.0, abs_tol=1e-12)


# ---------------------------------------------------------------------------
# change_slope — LandTrendr
# ---------------------------------------------------------------------------


def test_change_slope_lt_scales_both_segments():
    blob = _lt_blob()
    t = _t()
    brk = blob.coefficients["breakpoint"]
    s1 = blob.coefficients["slope_1"]
    s2 = blob.coefficients["slope_2"]
    alpha = 2.0
    result = change_slope(blob, alpha=alpha, t=t)
    assert len(result.values) == len(t)
    slope_after_1 = np.polyfit(t[:brk], result.values[:brk], 1)[0]
    assert abs(slope_after_1 - alpha * s1) < 1e-8


def test_change_slope_lt_zero_is_constant():
    blob = _lt_blob()
    result = change_slope(blob, alpha=0.0, t=_t())
    assert np.allclose(result.values, result.values[0], atol=1e-12)


# ---------------------------------------------------------------------------
# reverse_direction
# ---------------------------------------------------------------------------


def test_reverse_direction_etm_negates_slope():
    n = 10
    blob = _etm_blob(n=n, x0=0.0, rate=1.0)
    t = _t(n)
    result = reverse_direction(blob, t=t)
    expected = -1.0 * t
    assert np.allclose(result.values, expected, atol=1e-12)


def test_reverse_direction_twice_is_identity():
    blob = _etm_blob(x0=2.0, rate=0.3)
    t = _t()
    original_values = blob.reassemble()
    negated_blob = DecompositionBlob(
        method="ETM",
        components={
            "x0": np.full(len(t), 2.0),
            "linear_rate": -0.3 * t,
            "residual": np.zeros(len(t)),
        },
        coefficients={"x0": 2.0, "linear_rate": -0.3},
    )
    r_double = reverse_direction(negated_blob, t=t)
    assert np.allclose(r_double.values, original_values, atol=1e-12)


def test_reverse_direction_relabel_preserved():
    result = reverse_direction(_etm_blob(), t=_t())
    assert result.relabel.rule_class == "PRESERVED"
    assert result.relabel.new_shape == "trend"


def test_reverse_direction_op_name():
    result = reverse_direction(_etm_blob(), t=_t())
    assert result.op_name == "reverse_direction"


def test_reverse_direction_does_not_mutate_blob():
    blob = _etm_blob(rate=0.5)
    reverse_direction(blob, t=_t())
    assert math.isclose(blob.coefficients["linear_rate"], 0.5, abs_tol=1e-12)


def test_reverse_direction_lt():
    blob = _lt_blob()
    t = _t()
    result = reverse_direction(blob, t=t)
    assert len(result.values) == len(t)
    assert result.relabel.rule_class == "PRESERVED"


# ---------------------------------------------------------------------------
# linearise
# ---------------------------------------------------------------------------


def test_linearise_transitions_to_etm():
    blob = _lt_blob()
    t = _t()
    X = blob.reassemble()
    result = linearise(blob, X_orig=X, t=t)
    assert result.relabel.rule_class == "PRESERVED"
    assert result.relabel.new_shape == "trend"


def test_linearise_result_is_linear():
    blob = _etm_blob(x0=1.0, rate=0.3)
    t = _t(20)
    X = 1.0 + 0.3 * t
    result = linearise(blob, X_orig=X, t=t)
    slope, _ = np.polyfit(t, result.values, 1)
    assert abs(slope - 0.3) < 0.01


def test_linearise_robust_outlier_slope():
    """Theil-Sen should recover slope 1.0 even with large outliers (Sen 1968)."""
    n = 30
    t = _t(n)
    X = 1.0 * t + np.zeros(n)
    X[5] = 500.0
    X[15] = -500.0
    blob = _etm_blob(n=n, x0=0.0, rate=0.5)
    result = linearise(blob, X_orig=X, t=t)
    slope, _ = np.polyfit(t, result.values, 1)
    assert abs(slope - 1.0) < 0.15


def test_linearise_collapses_lt_to_single_fit():
    blob = _lt_blob()
    t = _t()
    X = blob.reassemble()
    result = linearise(blob, X_orig=X, t=t)
    slope, _ = np.polyfit(t, result.values, 1)
    assert np.isfinite(slope)


def test_linearise_does_not_mutate_blob():
    blob = _lt_blob()
    original_method = blob.method
    linearise(blob, X_orig=blob.reassemble(), t=_t())
    assert blob.method == original_method


def test_linearise_op_name():
    blob = _etm_blob()
    result = linearise(blob, X_orig=blob.reassemble(), t=_t())
    assert result.op_name == "linearise"


def test_linearise_length_preserved():
    n = 25
    blob = _etm_blob(n=n)
    result = linearise(blob, X_orig=blob.reassemble(), t=_t(n))
    assert len(result.values) == n


# ---------------------------------------------------------------------------
# extrapolate
# ---------------------------------------------------------------------------


def test_extrapolate_etm_at_t0_is_x0():
    blob = _etm_blob(x0=3.0, rate=0.5)
    t_ext = np.arange(30, dtype=np.float64)
    result = extrapolate(blob, t_extended=t_ext)
    assert math.isclose(float(result.values[0]), 3.0, abs_tol=1e-12)


def test_extrapolate_etm_slope_preserved():
    blob = _etm_blob(x0=0.0, rate=2.0)
    t_ext = np.arange(15, dtype=np.float64)
    result = extrapolate(blob, t_extended=t_ext)
    slope, _ = np.polyfit(t_ext, result.values, 1)
    assert abs(slope - 2.0) < 1e-10


def test_extrapolate_beyond_segment_length():
    blob = _etm_blob(x0=1.0, rate=1.0)
    t_ext = np.arange(20, 40, dtype=np.float64)
    result = extrapolate(blob, t_extended=t_ext)
    assert len(result.values) == 20


def test_extrapolate_etm_nonzero_start_correct_value():
    """x(t) = x0 + rate*t (absolute t); at t=20 value should be x0 + rate*20."""
    blob = _etm_blob(x0=1.0, rate=0.5)
    t_ext = np.arange(20, 40, dtype=np.float64)
    result = extrapolate(blob, t_extended=t_ext)
    expected_at_20 = 1.0 + 0.5 * 20.0
    assert math.isclose(float(result.values[0]), expected_at_20, abs_tol=1e-10)


def test_extrapolate_lt_nonzero_start_correct_value():
    """LandTrendr extrapolate uses absolute t: i2 + s2 * t_ext."""
    blob = _lt_blob()
    i2 = blob.coefficients["intercept_2"]
    s2 = blob.coefficients["slope_2"]
    t_ext = np.arange(25, 35, dtype=np.float64)
    result = extrapolate(blob, t_extended=t_ext)
    expected_at_25 = i2 + s2 * 25.0
    assert math.isclose(float(result.values[0]), expected_at_25, abs_tol=1e-10)


def test_extrapolate_relabel_preserved():
    result = extrapolate(_etm_blob(), t_extended=_t(30))
    assert result.relabel.rule_class == "PRESERVED"
    assert result.relabel.new_shape == "trend"


def test_extrapolate_op_name():
    result = extrapolate(_etm_blob(), t_extended=_t())
    assert result.op_name == "extrapolate"


def test_extrapolate_does_not_mutate_blob():
    blob = _etm_blob(x0=5.0, rate=0.1)
    extrapolate(blob, t_extended=_t(30))
    assert math.isclose(blob.coefficients["x0"], 5.0, abs_tol=1e-12)


def test_extrapolate_lt_returns_correct_length():
    blob = _lt_blob()
    t_ext = np.arange(30, dtype=np.float64)
    result = extrapolate(blob, t_extended=t_ext)
    assert len(result.values) == 30


def test_extrapolate_lt_is_linear():
    blob = _lt_blob()
    t_ext = np.arange(25, dtype=np.float64)
    result = extrapolate(blob, t_extended=t_ext)
    slope, _ = np.polyfit(t_ext, result.values, 1)
    assert np.isfinite(slope)


# ---------------------------------------------------------------------------
# add_acceleration
# ---------------------------------------------------------------------------


def test_add_acceleration_etm_values_correct():
    n = 10
    t = _t(n)
    blob = _etm_blob(n=n, x0=1.0, rate=0.0)
    c = 0.5
    result = add_acceleration(blob, c=c, t=t)
    expected = 1.0 + c * t ** 2
    assert np.allclose(result.values, expected, atol=1e-12)


def test_add_acceleration_relabel_preserved():
    result = add_acceleration(_etm_blob(), c=0.1, t=_t())
    assert result.relabel.rule_class == "PRESERVED"
    assert result.relabel.new_shape == "trend"


def test_add_acceleration_op_name():
    result = add_acceleration(_etm_blob(), c=0.1, t=_t())
    assert result.op_name == "add_acceleration"


def test_add_acceleration_zero_c_is_identity():
    blob = _etm_blob(x0=2.0, rate=0.3)
    t = _t()
    original = blob.reassemble()
    result = add_acceleration(blob, c=0.0, t=t)
    assert np.allclose(result.values, original, atol=1e-12)


def test_add_acceleration_does_not_mutate_blob():
    blob = _etm_blob()
    add_acceleration(blob, c=0.5, t=_t())
    assert "acceleration" not in blob.components


def test_add_acceleration_lt_returns_correct_length():
    blob = _lt_blob()
    t = _t()
    result = add_acceleration(blob, c=0.2, t=t)
    assert len(result.values) == len(t)


def test_add_acceleration_stores_coefficient():
    blob = _etm_blob()
    c = 0.7
    result = add_acceleration(blob, c=c, t=_t())
    assert result.relabel.rule_class == "PRESERVED"


def test_add_acceleration_lt_adds_curvature():
    blob = _lt_blob()
    t = _t()
    original_values = blob.reassemble()
    result = add_acceleration(blob, c=0.3, t=t)
    diff = result.values - original_values
    assert diff[-1] > diff[0]
