"""Tests for Tier-1 amplitude atoms: scale, offset, mute_zero (OP-010)."""

import copy
import math
import logging

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.operations.tier1.amplitude import AmplitudeOpResult, mute_zero, offset, scale


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _plateau_blob(n: int = 20, level: float = 0.5) -> DecompositionBlob:
    """Constant (plateau) blob."""
    arr = np.full(n, level)
    residual = np.zeros(n)
    return DecompositionBlob(
        method="Constant",
        components={"trend": arr.copy(), "residual": residual.copy()},
        coefficients={"level": level},
        residual=residual.copy(),
    )


def _trend_blob(n: int = 20) -> DecompositionBlob:
    """ETM-style trend blob with x0 and linear_rate."""
    t = np.arange(n, dtype=float)
    x0 = np.full(n, 1.0)
    linear = t * 0.1
    residual = np.zeros(n)
    return DecompositionBlob(
        method="ETM",
        components={"x0": x0.copy(), "linear_rate": linear.copy(), "residual": residual.copy()},
        coefficients={"x0": 1.0, "linear_rate": 0.1},
        residual=residual.copy(),
    )


def _cycle_stl_blob(n: int = 24) -> DecompositionBlob:
    """STL-style cycle blob with trend and seasonal."""
    t = np.arange(n, dtype=float)
    trend = np.zeros(n)
    seasonal = np.sin(2 * math.pi * t / 6)
    residual = np.zeros(n)
    return DecompositionBlob(
        method="STL",
        components={"trend": trend.copy(), "seasonal": seasonal.copy(), "residual": residual.copy()},
        coefficients={},
        residual=residual.copy(),
    )


def _cycle_mstl_blob(n: int = 24) -> DecompositionBlob:
    """MSTL-style blob with trend and two seasonal_ components."""
    t = np.arange(n, dtype=float)
    trend = np.zeros(n)
    s1 = np.sin(2 * math.pi * t / 6)
    s2 = 0.5 * np.sin(2 * math.pi * t / 12)
    residual = np.zeros(n)
    return DecompositionBlob(
        method="MSTL",
        components={
            "trend": trend.copy(),
            "seasonal_6": s1.copy(),
            "seasonal_12": s2.copy(),
            "residual": residual.copy(),
        },
        coefficients={},
        residual=residual.copy(),
    )


def _etm_blob_with_harmonics(n: int = 24) -> DecompositionBlob:
    """ETM blob with harmonic components for scale testing."""
    t = np.arange(n, dtype=float)
    x0 = np.full(n, 1.0)
    linear = t * 0.05
    sin_comp = np.sin(2 * math.pi * t / 6)
    cos_comp = np.cos(2 * math.pi * t / 6)
    residual = np.zeros(n)
    return DecompositionBlob(
        method="ETM",
        components={
            "x0": x0.copy(),
            "linear_rate": linear.copy(),
            "sin_6": sin_comp.copy(),
            "cos_6": cos_comp.copy(),
            "residual": residual.copy(),
        },
        coefficients={
            "x0": 1.0,
            "linear_rate": 0.05,
            "sin_6": 1.0,
            "cos_6": 1.0,
        },
        residual=residual.copy(),
    )


def _unknown_blob(n: int = 20) -> DecompositionBlob:
    """Blob with an unrecognised method to test fallback path."""
    arr = np.ones(n) * 0.3
    return DecompositionBlob(
        method="GrAtSiD",
        components={"signal": arr.copy(), "residual": np.zeros(n)},
        coefficients={},
    )


# ---------------------------------------------------------------------------
# scale — identity
# ---------------------------------------------------------------------------


def test_scale_identity_no_blob():
    arr = np.array([1.0, 2.0, 3.0])
    result = scale(arr, blob=None, alpha=1.0, pivot="mean")
    assert np.allclose(result.values, arr)


def test_scale_identity_plateau_blob():
    blob = _plateau_blob()
    original = blob.reassemble().copy()
    result = scale(original, blob=blob, alpha=1.0)
    assert np.allclose(result.values, original, atol=1e-10)


def test_scale_identity_stl_blob():
    blob = _cycle_stl_blob()
    original = blob.reassemble().copy()
    result = scale(original, blob=blob, alpha=1.0)
    assert np.allclose(result.values, original, atol=1e-10)


# ---------------------------------------------------------------------------
# scale — raw-value pivot variants
# ---------------------------------------------------------------------------


def test_scale_raw_pivot_mean():
    arr = np.array([0.0, 1.0, 2.0])
    result = scale(arr, None, alpha=2.0, pivot="mean")
    mean = 1.0
    expected = mean + 2.0 * (arr - mean)
    assert np.allclose(result.values, expected)


def test_scale_raw_pivot_min():
    arr = np.array([1.0, 2.0, 3.0])
    result = scale(arr, None, alpha=2.0, pivot="min")
    expected = 1.0 + 2.0 * (arr - 1.0)
    assert np.allclose(result.values, expected)


def test_scale_raw_pivot_zero():
    arr = np.array([1.0, 2.0, 3.0])
    result = scale(arr, None, alpha=3.0, pivot="zero")
    assert np.allclose(result.values, arr * 3.0)


def test_scale_unknown_pivot_raises():
    with pytest.raises(ValueError, match="unknown pivot"):
        scale(np.array([1.0, 2.0]), None, alpha=1.0, pivot="median")


# ---------------------------------------------------------------------------
# scale — alpha=0 relabel → DETERMINISTIC(plateau)
# ---------------------------------------------------------------------------


def test_scale_alpha_zero_relabel_plateau():
    arr = np.array([1.0, 2.0, 3.0])
    result = scale(arr, None, alpha=0.0, pre_shape="trend")
    assert result.relabel.rule_class == "DETERMINISTIC"
    assert result.relabel.new_shape == "plateau"


def test_scale_alpha_zero_collapses_to_flat():
    arr = np.array([0.0, 1.0, 2.0])
    result = scale(arr, None, alpha=0.0, pivot="mean")
    assert np.allclose(result.values, np.full_like(arr, np.mean(arr)))


def test_scale_alpha_nonzero_relabel_preserved():
    result = scale(np.array([1.0, 2.0]), None, alpha=2.0, pre_shape="trend")
    assert result.relabel.rule_class == "PRESERVED"
    assert result.relabel.new_shape == "trend"


# ---------------------------------------------------------------------------
# scale — decomposition-aware blobs
# ---------------------------------------------------------------------------


def test_scale_plateau_blob_scales_trend_component():
    blob = _plateau_blob(level=1.0)
    original_trend = blob.components["trend"].copy()
    result = scale(np.ones(20), blob=blob, alpha=2.0)
    assert np.allclose(blob.components["trend"], original_trend * 2.0)
    assert np.allclose(result.values, blob.reassemble())


def test_scale_stl_blob_scales_only_seasonal():
    blob = _cycle_stl_blob()
    trend_before = blob.components["trend"].copy()
    result = scale(blob.reassemble(), blob=blob, alpha=2.0)
    assert np.allclose(blob.components["trend"], trend_before)
    assert result.relabel.rule_class == "PRESERVED"


def test_scale_mstl_blob_scales_all_seasonal_keys():
    blob = _cycle_mstl_blob()
    s1_before = blob.components["seasonal_6"].copy()
    s2_before = blob.components["seasonal_12"].copy()
    scale(blob.reassemble(), blob=blob, alpha=3.0)
    assert np.allclose(blob.components["seasonal_6"], s1_before * 3.0)
    assert np.allclose(blob.components["seasonal_12"], s2_before * 3.0)


def test_scale_etm_blob_scales_harmonics_only():
    blob = _etm_blob_with_harmonics()
    x0_before = blob.components["x0"].copy()
    sin_before = blob.components["sin_6"].copy()
    scale(blob.reassemble(), blob=blob, alpha=0.5)
    assert np.allclose(blob.components["x0"], x0_before)
    assert np.allclose(blob.components["sin_6"], sin_before * 0.5)
    assert math.isclose(blob.coefficients["sin_6"], 0.5, rel_tol=1e-9)


def test_scale_blob_mutates_in_place():
    blob = _plateau_blob(level=1.0)
    blob_before_trend = blob.components["trend"].copy()
    scale(np.ones(20), blob=blob, alpha=5.0)
    assert not np.allclose(blob.components["trend"], blob_before_trend)


def test_scale_blob_deepcopy_untouched():
    blob = _plateau_blob(level=1.0)
    blob_copy = copy.deepcopy(blob)
    scale(np.ones(20), blob=blob, alpha=2.0)
    assert np.allclose(blob_copy.components["trend"], np.ones(20) * 1.0)


def test_scale_unknown_blob_method_falls_back_raw(caplog):
    arr = np.array([1.0, 2.0, 3.0])
    blob = _unknown_blob(n=3)
    with caplog.at_level(logging.WARNING, logger="app.services.operations.tier1.amplitude"):
        result = scale(arr, blob=blob, alpha=2.0, pivot="zero")
    assert np.allclose(result.values, arr * 2.0)
    assert any("falling back" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# offset — identity
# ---------------------------------------------------------------------------


def test_offset_identity_no_blob():
    arr = np.array([1.0, 2.0, 3.0])
    result = offset(arr, blob=None, delta=0.0)
    assert np.allclose(result.values, arr)


def test_offset_identity_plateau_blob():
    blob = _plateau_blob()
    original = blob.reassemble().copy()
    result = offset(original, blob=blob, delta=0.0)
    assert np.allclose(result.values, original)


# ---------------------------------------------------------------------------
# offset — raw-value
# ---------------------------------------------------------------------------


def test_offset_raw_adds_delta():
    arr = np.array([1.0, 2.0, 3.0])
    result = offset(arr, blob=None, delta=5.0)
    assert np.allclose(result.values, arr + 5.0)


def test_offset_relabel_always_preserved():
    result = offset(np.array([1.0, 2.0]), blob=None, delta=10.0, pre_shape="cycle")
    assert result.relabel.rule_class == "PRESERVED"
    assert result.relabel.new_shape == "cycle"


# ---------------------------------------------------------------------------
# offset — decomposition-aware blobs
# ---------------------------------------------------------------------------


def test_offset_plateau_blob_shifts_trend_and_coefficient():
    blob = _plateau_blob(level=0.5)
    offset(np.full(20, 0.5), blob=blob, delta=1.0)
    assert math.isclose(blob.coefficients["level"], 1.5, rel_tol=1e-9)
    assert np.allclose(blob.components["trend"], np.full(20, 1.5))


def test_offset_etm_blob_shifts_x0():
    blob = _trend_blob()
    offset(blob.reassemble(), blob=blob, delta=3.0)
    assert math.isclose(blob.coefficients["x0"], 4.0, rel_tol=1e-9)
    assert np.allclose(blob.components["x0"], np.full(20, 4.0))


def test_offset_stl_blob_shifts_trend_component():
    blob = _cycle_stl_blob()
    trend_before = blob.components["trend"].copy()
    offset(blob.reassemble(), blob=blob, delta=2.0)
    assert np.allclose(blob.components["trend"], trend_before + 2.0)


def test_offset_mstl_blob_shifts_trend_component():
    blob = _cycle_mstl_blob()
    trend_before = blob.components["trend"].copy()
    offset(blob.reassemble(), blob=blob, delta=-1.5)
    assert np.allclose(blob.components["trend"], trend_before - 1.5)


def test_offset_unknown_blob_falls_back_raw(caplog):
    arr = np.array([1.0, 2.0, 3.0])
    blob = _unknown_blob(n=3)
    with caplog.at_level(logging.WARNING, logger="app.services.operations.tier1.amplitude"):
        result = offset(arr, blob=blob, delta=1.0)
    assert np.allclose(result.values, arr + 1.0)
    assert any("falling back" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# mute_zero
# ---------------------------------------------------------------------------


def test_mute_zero_fill_zero_returns_zeros():
    arr = np.array([1.0, 2.0, 3.0])
    result = mute_zero(arr, blob=None, fill="zero")
    assert np.allclose(result.values, np.zeros(3))


def test_mute_zero_fill_global_mean():
    arr = np.array([1.0, 2.0, 3.0])
    result = mute_zero(arr, blob=None, fill="global_mean", mu_global=5.0)
    assert np.allclose(result.values, np.full(3, 5.0))


def test_mute_zero_relabel_deterministic_plateau():
    arr = np.array([1.0, 2.0, 3.0])
    result = mute_zero(arr, blob=None, fill="zero", pre_shape="trend")
    assert result.relabel.rule_class == "DETERMINISTIC"
    assert result.relabel.new_shape == "plateau"


def test_mute_zero_relabel_plateau_for_global_mean_too():
    result = mute_zero(np.ones(5), blob=None, fill="global_mean", mu_global=2.5, pre_shape="cycle")
    assert result.relabel.new_shape == "plateau"


def test_mute_zero_global_mean_without_mu_raises():
    with pytest.raises(ValueError, match="mu_global"):
        mute_zero(np.array([1.0, 2.0]), blob=None, fill="global_mean")


def test_mute_zero_unknown_fill_raises():
    with pytest.raises(ValueError, match="unknown fill"):
        mute_zero(np.array([1.0, 2.0]), blob=None, fill="median")


def test_mute_zero_updates_blob_components():
    blob = _plateau_blob()
    result = mute_zero(np.full(20, 0.5), blob=blob, fill="zero")
    assert "muted" in blob.components
    assert np.allclose(blob.components["muted"], np.zeros(20))
    assert blob.coefficients["fill"] == "zero"


def test_mute_zero_blob_mutation_deepcopy_check():
    blob = _cycle_stl_blob()
    blob_copy = copy.deepcopy(blob)
    mute_zero(blob.reassemble(), blob=blob, fill="zero")
    assert "seasonal" in blob_copy.components
    assert "muted" not in blob_copy.components


def test_mute_zero_plus_offset_gives_constant():
    arr = np.array([1.0, 2.0, 3.0])
    mu = 7.0
    r1 = mute_zero(arr, blob=None, fill="zero")
    r2 = offset(r1.values, blob=None, delta=mu)
    assert np.allclose(r2.values, np.full(3, mu))


# ---------------------------------------------------------------------------
# Return type and tier
# ---------------------------------------------------------------------------


def test_result_is_amplitude_op_result():
    result = scale(np.array([1.0, 2.0]), None, alpha=1.0)
    assert isinstance(result, AmplitudeOpResult)
    assert result.tier == 1


def test_scale_op_name():
    result = scale(np.array([1.0]), None, alpha=1.0)
    assert result.op_name == "scale"


def test_offset_op_name():
    result = offset(np.array([1.0]), None, delta=0.0)
    assert result.op_name == "offset"


def test_mute_zero_op_name():
    result = mute_zero(np.array([1.0]), None)
    assert result.op_name == "mute_zero"
