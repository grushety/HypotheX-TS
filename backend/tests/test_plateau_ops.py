"""Tests for Tier-2 plateau ops: raise_lower, invert, replace_with_trend,
replace_with_cycle, tilt_detrend (OP-020).
"""

import copy
import math

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.operations.tier2.plateau import (
    Tier2OpResult,
    invert,
    raise_lower,
    replace_with_cycle,
    replace_with_trend,
    tilt_detrend,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_blob(n: int = 20, level: float = 5.0, residual_slope: float = 0.0) -> DecompositionBlob:
    """Synthetic Constant blob with optional residual slope."""
    t = np.arange(n, dtype=np.float64)
    trend = np.full(n, level, dtype=np.float64)
    residual = residual_slope * t
    return DecompositionBlob(
        method="Constant",
        components={"trend": trend, "residual": residual},
        coefficients={"level": level},
        residual=residual,
        fit_metadata={"rmse": 0.0, "rank": 1, "n_params": 1, "convergence": True},
    )


def _t(n: int = 20) -> np.ndarray:
    return np.arange(n, dtype=np.float64)


# ---------------------------------------------------------------------------
# Tier2OpResult — shared type
# ---------------------------------------------------------------------------


def test_tier2_result_type_from_raise_lower():
    result = raise_lower(copy.deepcopy(_make_blob()), delta=1.0)
    assert isinstance(result, Tier2OpResult)


def test_tier2_result_tier_is_2():
    result = raise_lower(copy.deepcopy(_make_blob()), delta=0.0)
    assert result.tier == 2


# ---------------------------------------------------------------------------
# raise_lower — additive delta
# ---------------------------------------------------------------------------


def test_raise_lower_delta_increases_level():
    blob = copy.deepcopy(_make_blob(level=5.0))
    result = raise_lower(blob, delta=2.0)
    assert np.allclose(result.values, 7.0, atol=1e-12)


def test_raise_lower_delta_decreases_level():
    blob = copy.deepcopy(_make_blob(level=5.0))
    result = raise_lower(blob, delta=-3.0)
    assert np.allclose(result.values, 2.0, atol=1e-12)


def test_raise_lower_delta_zero_is_identity():
    blob = copy.deepcopy(_make_blob(level=5.0))
    result = raise_lower(blob, delta=0.0)
    assert np.allclose(result.values, 5.0, atol=1e-12)


def test_raise_lower_does_not_mutate_caller_blob():
    blob = _make_blob(level=5.0)
    raise_lower(blob, delta=1.0)
    assert math.isclose(blob.coefficients["level"], 5.0, abs_tol=1e-12)


def test_raise_lower_delta_length_preserved():
    n = 25
    blob = copy.deepcopy(_make_blob(n=n))
    result = raise_lower(blob, delta=1.0)
    assert len(result.values) == n


# ---------------------------------------------------------------------------
# raise_lower — multiplicative alpha
# ---------------------------------------------------------------------------


def test_raise_lower_alpha_no_pivot_multiplies():
    blob = copy.deepcopy(_make_blob(level=4.0))
    result = raise_lower(blob, alpha=0.5)
    assert np.allclose(result.values, 6.0, atol=1e-12)


def test_raise_lower_alpha_with_pivot():
    blob = copy.deepcopy(_make_blob(level=5.0))
    result = raise_lower(blob, alpha=1.0, pivot_mean=3.0)
    expected = 3.0 + 2.0 * (5.0 - 3.0)
    assert np.allclose(result.values, expected, atol=1e-12)


def test_raise_lower_alpha_negative_shrinks():
    blob = copy.deepcopy(_make_blob(level=10.0))
    result = raise_lower(blob, alpha=-0.5)
    assert np.allclose(result.values, 5.0, atol=1e-12)


def test_raise_lower_alpha_zero_is_identity_at_zero_pivot():
    blob = copy.deepcopy(_make_blob(level=6.0))
    result = raise_lower(blob, alpha=0.0)
    assert np.allclose(result.values, 6.0, atol=1e-12)


# ---------------------------------------------------------------------------
# raise_lower — error handling
# ---------------------------------------------------------------------------


def test_raise_lower_neither_delta_nor_alpha_raises():
    with pytest.raises(ValueError, match="exactly one"):
        raise_lower(copy.deepcopy(_make_blob()))


def test_raise_lower_both_delta_and_alpha_raises():
    with pytest.raises(ValueError, match="exactly one"):
        raise_lower(copy.deepcopy(_make_blob()), delta=1.0, alpha=0.5)


# ---------------------------------------------------------------------------
# raise_lower — relabeling
# ---------------------------------------------------------------------------


def test_raise_lower_relabel_preserved():
    result = raise_lower(copy.deepcopy(_make_blob()), delta=1.0)
    assert result.relabel.rule_class == "PRESERVED"
    assert result.relabel.needs_resegment is False


def test_raise_lower_pre_shape_propagated():
    result = raise_lower(copy.deepcopy(_make_blob()), delta=1.0, pre_shape="plateau")
    assert result.relabel.new_shape == "plateau"


def test_raise_lower_op_name():
    result = raise_lower(copy.deepcopy(_make_blob()), delta=1.0)
    assert result.op_name == "raise_lower"


# ---------------------------------------------------------------------------
# invert
# ---------------------------------------------------------------------------


def test_invert_correct_values():
    blob = copy.deepcopy(_make_blob(level=5.0))
    result = invert(blob, mu_global=4.0)
    assert np.allclose(result.values, 3.0, atol=1e-12)


def test_invert_at_mu_is_identity():
    blob = copy.deepcopy(_make_blob(level=5.0))
    result = invert(blob, mu_global=5.0)
    assert np.allclose(result.values, 5.0, atol=1e-12)


def test_invert_twice_is_identity():
    blob = copy.deepcopy(_make_blob(level=3.5))
    r1 = invert(blob, mu_global=2.0)
    blob2 = DecompositionBlob(
        method="Constant",
        components={"trend": r1.values, "residual": np.zeros_like(r1.values)},
        coefficients={"level": float(r1.values[0])},
    )
    r2 = invert(blob2, mu_global=2.0)
    assert np.allclose(r2.values, 3.5, atol=1e-12)


def test_invert_does_not_mutate_blob():
    blob = copy.deepcopy(_make_blob(level=5.0))
    original_level = blob.coefficients["level"]
    invert(blob, mu_global=3.0)
    assert math.isclose(blob.coefficients["level"], original_level, abs_tol=1e-12)


def test_invert_relabel_preserved():
    result = invert(copy.deepcopy(_make_blob()), mu_global=0.0)
    assert result.relabel.rule_class == "PRESERVED"


def test_invert_op_name():
    result = invert(copy.deepcopy(_make_blob()), mu_global=0.0)
    assert result.op_name == "invert"


def test_invert_length_preserved():
    n = 30
    result = invert(copy.deepcopy(_make_blob(n=n)), mu_global=1.0)
    assert len(result.values) == n


# ---------------------------------------------------------------------------
# replace_with_trend
# ---------------------------------------------------------------------------


def test_replace_with_trend_values_correct():
    n = 10
    blob = copy.deepcopy(_make_blob(n=n, level=5.0))
    t = _t(n)
    result = replace_with_trend(blob, beta=0.1, t=t)
    expected = 5.0 + 0.1 * t
    assert np.allclose(result.values, expected, atol=1e-12)


def test_replace_with_trend_first_value_equals_plateau_level():
    blob = copy.deepcopy(_make_blob(level=3.0))
    result = replace_with_trend(blob, beta=0.5, t=_t())
    assert math.isclose(float(result.values[0]), 3.0, abs_tol=1e-12)


def test_replace_with_trend_does_not_mutate_caller_blob():
    blob = _make_blob()
    replace_with_trend(blob, beta=0.2, t=_t())
    assert blob.method == "Constant"


def test_replace_with_trend_result_encodes_etm_intercept():
    n = 10
    result = replace_with_trend(_make_blob(n=n, level=4.0), beta=0.3, t=_t(n))
    assert math.isclose(float(result.values[0]), 4.0, abs_tol=1e-12)


def test_replace_with_trend_zero_beta_returns_flat():
    blob = copy.deepcopy(_make_blob(level=7.0))
    result = replace_with_trend(blob, beta=0.0, t=_t())
    assert np.allclose(result.values, 7.0, atol=1e-12)


def test_replace_with_trend_relabel_deterministic_trend():
    result = replace_with_trend(copy.deepcopy(_make_blob()), beta=0.1, t=_t())
    assert result.relabel.rule_class == "DETERMINISTIC"
    assert result.relabel.new_shape == "trend"
    assert result.relabel.needs_resegment is False


def test_replace_with_trend_op_name():
    result = replace_with_trend(copy.deepcopy(_make_blob()), beta=0.1, t=_t())
    assert result.op_name == "replace_with_trend"


def test_replace_with_trend_length_preserved():
    n = 15
    result = replace_with_trend(copy.deepcopy(_make_blob(n=n)), beta=1.0, t=_t(n))
    assert len(result.values) == n


# ---------------------------------------------------------------------------
# replace_with_cycle
# ---------------------------------------------------------------------------


def test_replace_with_cycle_trend_baseline_is_level():
    n = 8
    level = 5.0
    blob = copy.deepcopy(_make_blob(n=n, level=level))
    t = _t(n)
    result = replace_with_cycle(blob, amplitude=0.0, period=4.0, phase=0.0, t=t)
    assert np.allclose(result.values, level, atol=1e-12)


def test_replace_with_cycle_seasonal_amplitude_correct():
    n = 8
    level = 0.0
    amplitude = 2.0
    period = 4.0
    blob = copy.deepcopy(_make_blob(n=n, level=level))
    t = _t(n)
    result = replace_with_cycle(blob, amplitude=amplitude, period=period, phase=0.0, t=t)
    expected_seasonal = amplitude * np.sin(2.0 * np.pi * t / period)
    assert np.allclose(result.values, expected_seasonal, atol=1e-10)


def test_replace_with_cycle_does_not_mutate_caller_blob():
    blob = _make_blob()
    replace_with_cycle(blob, amplitude=1.0, period=5.0, phase=0.0, t=_t())
    assert blob.method == "Constant"


def test_replace_with_cycle_zero_period_raises():
    with pytest.raises(ValueError, match="period must be > 0"):
        replace_with_cycle(_make_blob(), amplitude=1.0, period=0.0, phase=0.0, t=_t())


def test_replace_with_cycle_negative_period_raises():
    with pytest.raises(ValueError, match="period must be > 0"):
        replace_with_cycle(_make_blob(), amplitude=1.0, period=-4.0, phase=0.0, t=_t())


def test_replace_with_cycle_relabel_deterministic_cycle():
    result = replace_with_cycle(
        copy.deepcopy(_make_blob()), amplitude=1.0, period=4.0, phase=0.0, t=_t()
    )
    assert result.relabel.rule_class == "DETERMINISTIC"
    assert result.relabel.new_shape == "cycle"
    assert result.relabel.needs_resegment is False


def test_replace_with_cycle_op_name():
    result = replace_with_cycle(
        copy.deepcopy(_make_blob()), amplitude=1.0, period=4.0, phase=0.0, t=_t()
    )
    assert result.op_name == "replace_with_cycle"


def test_replace_with_cycle_length_preserved():
    n = 24
    result = replace_with_cycle(
        copy.deepcopy(_make_blob(n=n)), amplitude=1.0, period=6.0, phase=0.0, t=_t(n)
    )
    assert len(result.values) == n


def test_replace_with_cycle_phase_shift():
    n = 12
    period = 6.0
    blob0 = copy.deepcopy(_make_blob(n=n, level=0.0))
    blob1 = copy.deepcopy(_make_blob(n=n, level=0.0))
    t = _t(n)
    r0 = replace_with_cycle(blob0, amplitude=1.0, period=period, phase=0.0, t=t)
    r1 = replace_with_cycle(blob1, amplitude=1.0, period=period, phase=np.pi / 2, t=t)
    assert not np.allclose(r0.values, r1.values, atol=1e-6)


# ---------------------------------------------------------------------------
# tilt_detrend
# ---------------------------------------------------------------------------


def test_tilt_detrend_removes_local_slope():
    n = 20
    beta = 0.3
    t = _t(n)
    blob = copy.deepcopy(_make_blob(n=n, level=5.0, residual_slope=beta))
    result = tilt_detrend(blob, beta_local=beta, t=t)
    slope, _ = np.polyfit(t, result.values, 1)
    assert abs(slope) < 1e-10


def test_tilt_detrend_flat_blob_subtracts_trend():
    n = 10
    t = _t(n)
    blob = copy.deepcopy(_make_blob(n=n, level=5.0))
    beta = 0.2
    result = tilt_detrend(blob, beta_local=beta, t=t)
    expected = 5.0 - beta * t
    assert np.allclose(result.values, expected, atol=1e-12)


def test_tilt_detrend_zero_beta_is_identity():
    blob = copy.deepcopy(_make_blob(level=3.0))
    t = _t()
    result = tilt_detrend(blob, beta_local=0.0, t=t)
    assert np.allclose(result.values, 3.0, atol=1e-12)


def test_tilt_detrend_does_not_mutate_blob():
    blob = copy.deepcopy(_make_blob(level=5.0))
    original_level = blob.coefficients["level"]
    tilt_detrend(blob, beta_local=0.5, t=_t())
    assert math.isclose(blob.coefficients["level"], original_level, abs_tol=1e-12)


def test_tilt_detrend_relabel_preserved():
    result = tilt_detrend(copy.deepcopy(_make_blob()), beta_local=0.1, t=_t())
    assert result.relabel.rule_class == "PRESERVED"
    assert result.relabel.needs_resegment is False


def test_tilt_detrend_pre_shape_propagated():
    result = tilt_detrend(copy.deepcopy(_make_blob()), beta_local=0.1, t=_t(), pre_shape="plateau")
    assert result.relabel.new_shape == "plateau"


def test_tilt_detrend_op_name():
    result = tilt_detrend(copy.deepcopy(_make_blob()), beta_local=0.0, t=_t())
    assert result.op_name == "tilt_detrend"


def test_tilt_detrend_length_preserved():
    n = 30
    result = tilt_detrend(copy.deepcopy(_make_blob(n=n)), beta_local=0.5, t=_t(n))
    assert len(result.values) == n


# ---------------------------------------------------------------------------
# _level helper — edge cases
# ---------------------------------------------------------------------------


def test_level_extraction_from_trend_component_when_no_level_key():
    n = 10
    level = 7.3
    blob = DecompositionBlob(
        method="Constant",
        components={"trend": np.full(n, level)},
        coefficients={},
    )
    result = raise_lower(blob, delta=0.0)
    assert np.allclose(result.values, level, atol=1e-12)


def test_empty_components_and_no_level_key_raises():
    blob = DecompositionBlob(method="Constant", components={}, coefficients={})
    with pytest.raises(ValueError, match="no 'level' coefficient and no components"):
        raise_lower(blob, delta=1.0)
