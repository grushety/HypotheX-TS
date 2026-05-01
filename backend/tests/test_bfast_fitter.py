"""Tests for the BFAST decomposition fitter — SEG-015.

References
----------
Verbesselt, Hyndman, Newnham, Culvenor (2010) RSE 114(1):106–115.
Masiliūnas, Tsendbazar, Herold, Verbesselt (2021) Remote Sensing 13(16):3308.
Bai & Perron (2003) J. Applied Econometrics 18(1):1–22.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import FITTER_REGISTRY, _ensure_fitters_loaded
from app.services.decomposition.fitters.bfast import (
    fit_bfast,
    fit_seasonal_dummies,
    fit_trend_with_bp,
)


RNG = np.random.default_rng(42)


# ---------------------------------------------------------------------------
# Synthetic NDVI fixtures
# ---------------------------------------------------------------------------


def _ndvi_with_break(
    n: int = 360,
    period: int = 24,
    bp: int = 180,
    pre_slope: float = 0.0,
    post_slope: float = 0.0,
    pre_level: float = 0.5,
    post_level: float = 0.2,
    seasonal_amp: float = 0.15,
    noise_sd: float = 0.0,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """NDVI-like signal with a single trend breakpoint at index ``bp``.

    Composition: piecewise-linear trend (level shift + optional slope change),
    plus a fundamental harmonic of period ``period``, plus optional Gaussian
    noise.  Default values mirror the AC fixture (n=360, period=24, bp=180).
    """
    t = np.arange(n, dtype=np.float64)
    trend = np.where(
        t < bp,
        pre_level + pre_slope * t,
        post_level + post_slope * (t - bp),
    )
    seasonal = seasonal_amp * np.sin(2.0 * np.pi * t / period)
    noise = (
        (rng if rng is not None else RNG).normal(scale=noise_sd, size=n)
        if noise_sd > 0
        else np.zeros(n)
    )
    return trend + seasonal + noise


# ---------------------------------------------------------------------------
# Registry / dispatcher integration
# ---------------------------------------------------------------------------


def test_bfast_registered():
    _ensure_fitters_loaded()
    assert "BFAST" in FITTER_REGISTRY
    assert FITTER_REGISTRY["BFAST"] is fit_bfast


def test_bfast_returns_decomposition_blob():
    X = _ndvi_with_break()
    blob = fit_bfast(X, period=24)
    assert isinstance(blob, DecompositionBlob)
    assert blob.method == "BFAST"


# ---------------------------------------------------------------------------
# Component shape / naming (SEG-014 STL interop)
# ---------------------------------------------------------------------------


def test_bfast_components_present_with_stl_compatible_keys():
    X = _ndvi_with_break()
    blob = fit_bfast(X, period=24)
    assert "trend" in blob.components
    assert "seasonal" in blob.components
    assert "residual" in blob.components


def test_bfast_components_have_correct_shape():
    n = 360
    X = _ndvi_with_break(n=n)
    blob = fit_bfast(X, period=24)
    for name, arr in blob.components.items():
        assert arr.shape == (n,), f"{name} has shape {arr.shape}"


# ---------------------------------------------------------------------------
# Reassembly (Verbesselt 2010 §2: residual ≡ X − T − S by construction)
# ---------------------------------------------------------------------------


def test_bfast_reassembly_matches_input_within_float_precision():
    X = _ndvi_with_break(noise_sd=0.05)
    blob = fit_bfast(X, period=24)
    np.testing.assert_allclose(blob.reassemble(), X, atol=1e-10)


def test_bfast_residual_field_matches_components_residual():
    X = _ndvi_with_break(noise_sd=0.05)
    blob = fit_bfast(X, period=24)
    np.testing.assert_array_equal(blob.residual, blob.components["residual"])


# ---------------------------------------------------------------------------
# Breakpoint detection accuracy (AC: bp=180 within ±3 timesteps)
# ---------------------------------------------------------------------------


def test_bfast_detects_known_breakpoint_within_tolerance():
    X = _ndvi_with_break(bp=180, pre_level=0.5, post_level=0.2, noise_sd=0.02)
    blob = fit_bfast(X, period=24)
    breaks = blob.coefficients["break_epochs"]
    assert breaks, "expected at least one detected breakpoint"
    closest = min(breaks, key=lambda bp: abs(bp - 180))
    assert abs(closest - 180) <= 3, f"detected {closest}, expected 180 ± 3"


def test_bfast_break_magnitude_has_correct_sign():
    X = _ndvi_with_break(bp=180, pre_level=0.5, post_level=0.2, noise_sd=0.02)
    blob = fit_bfast(X, period=24)
    mags = blob.coefficients["break_magnitudes"]
    assert mags, "expected at least one break magnitude"
    assert mags[0] < 0, f"expected negative magnitude (drop), got {mags[0]}"


def test_bfast_break_magnitude_count_matches_break_epochs():
    X = _ndvi_with_break(bp=180, pre_level=0.5, post_level=0.2, noise_sd=0.02)
    blob = fit_bfast(X, period=24)
    assert len(blob.coefficients["break_magnitudes"]) == len(
        blob.coefficients["break_epochs"]
    )


def test_bfast_no_break_for_smooth_series():
    """A pure seasonal + constant trend should yield zero breakpoints."""
    n = 360
    t = np.arange(n, dtype=np.float64)
    X = 0.5 + 0.15 * np.sin(2 * np.pi * t / 24)
    blob = fit_bfast(X, period=24)
    assert blob.coefficients["break_epochs"] == []
    assert blob.coefficients["break_magnitudes"] == []


# ---------------------------------------------------------------------------
# h-parameter respected (minimum segment size)
# ---------------------------------------------------------------------------


def test_bfast_h_parameter_recorded():
    X = _ndvi_with_break()
    blob = fit_bfast(X, period=24, h=0.20)
    assert blob.coefficients["h"] == pytest.approx(0.20)


def test_bfast_h_parameter_enforces_min_segment_size():
    """Every detected break must be ≥ h·n away from boundaries and from any
    other break (Verbesselt 2010 §2 minimum bandwidth h)."""
    n = 360
    h = 0.15
    h_min = max(2, int(round(h * n)))
    X = _ndvi_with_break(n=n, bp=180, pre_level=0.5, post_level=0.2, noise_sd=0.02)
    blob = fit_bfast(X, period=24, h=h)
    breaks = blob.coefficients["break_epochs"]
    for bp in breaks:
        assert bp >= h_min, f"break at {bp} closer than {h_min} to start"
        assert n - bp >= h_min, f"break at {bp} closer than {h_min} to end"
    sorted_breaks = sorted(breaks)
    for a, b in zip(sorted_breaks, sorted_breaks[1:]):
        assert b - a >= h_min, f"breaks {a},{b} closer than h_min={h_min}"


def test_bfast_invalid_h_raises():
    X = _ndvi_with_break()
    with pytest.raises(ValueError):
        fit_bfast(X, period=24, h=0.0)
    with pytest.raises(ValueError):
        fit_bfast(X, period=24, h=0.6)


# ---------------------------------------------------------------------------
# Variant switch (classical vs lite)
# ---------------------------------------------------------------------------


def test_bfast_variant_classical_default():
    X = _ndvi_with_break()
    blob = fit_bfast(X, period=24)
    assert blob.coefficients["variant"] == "classical"
    assert blob.fit_metadata["variant"] == "classical"


def test_bfast_variant_lite_uses_one_harmonic():
    X = _ndvi_with_break()
    blob = fit_bfast(X, period=24, variant="lite")
    assert blob.coefficients["variant"] == "lite"
    assert blob.coefficients["n_harmonics"] == 1
    assert blob.fit_metadata["iterations"] == 1


def test_bfast_variant_lite_caps_breakpoints_at_one():
    """Two real breakpoints in the data — lite must not return more than one."""
    n = 360
    t = np.arange(n, dtype=np.float64)
    trend = np.where(t < 120, 0.5, np.where(t < 240, 0.2, 0.6))
    seasonal = 0.15 * np.sin(2 * np.pi * t / 24)
    X = trend + seasonal + 0.02 * RNG.normal(size=n)
    blob = fit_bfast(X, period=24, variant="lite")
    assert len(blob.coefficients["break_epochs"]) <= 1


def test_bfast_classical_can_detect_multiple_breakpoints():
    """Classical variant should detect both of two real breakpoints."""
    n = 360
    t = np.arange(n, dtype=np.float64)
    trend = np.where(t < 120, 0.5, np.where(t < 240, 0.2, 0.6))
    seasonal = 0.15 * np.sin(2 * np.pi * t / 24)
    X = trend + seasonal + 0.02 * RNG.normal(size=n)
    blob = fit_bfast(X, period=24, h=0.10, variant="classical")
    breaks = sorted(blob.coefficients["break_epochs"])
    assert len(breaks) >= 2
    near_120 = any(abs(b - 120) <= 5 for b in breaks)
    near_240 = any(abs(b - 240) <= 5 for b in breaks)
    assert near_120 and near_240


def test_bfast_invalid_variant_raises():
    X = _ndvi_with_break()
    with pytest.raises(ValueError):
        fit_bfast(X, period=24, variant="quantum")


# ---------------------------------------------------------------------------
# Convergence / max_iter
# ---------------------------------------------------------------------------


def test_bfast_convergence_recorded_in_metadata():
    X = _ndvi_with_break(noise_sd=0.02)
    blob = fit_bfast(X, period=24, max_iter=10)
    assert "convergence" in blob.fit_metadata
    assert blob.fit_metadata["iterations"] >= 1
    assert blob.fit_metadata["iterations"] <= 10


def test_bfast_max_iter_one_runs_once_without_convergence_flag():
    X = _ndvi_with_break(noise_sd=0.02)
    blob = fit_bfast(X, period=24, max_iter=1)
    assert blob.fit_metadata["iterations"] == 1


def test_bfast_iterates_to_convergence_on_clean_signal():
    X = _ndvi_with_break(bp=180, pre_level=0.5, post_level=0.2, noise_sd=0.0)
    blob = fit_bfast(X, period=24, max_iter=20)
    assert blob.fit_metadata["convergence"] is True


# ---------------------------------------------------------------------------
# Coefficients exposed for OP-022 (Step ops)
# ---------------------------------------------------------------------------


def test_bfast_coefficients_have_op022_keys():
    X = _ndvi_with_break()
    blob = fit_bfast(X, period=24)
    assert "break_epochs" in blob.coefficients
    assert "break_magnitudes" in blob.coefficients
    assert "period" in blob.coefficients
    assert "h" in blob.coefficients


def test_bfast_break_epochs_are_python_ints():
    X = _ndvi_with_break()
    blob = fit_bfast(X, period=24)
    for bp in blob.coefficients["break_epochs"]:
        assert isinstance(bp, int)


def test_bfast_break_magnitudes_are_python_floats():
    X = _ndvi_with_break()
    blob = fit_bfast(X, period=24)
    for m in blob.coefficients["break_magnitudes"]:
        assert isinstance(m, float)


# ---------------------------------------------------------------------------
# Helpers — direct unit tests
# ---------------------------------------------------------------------------


def test_fit_seasonal_dummies_recovers_pure_sine():
    n = 240
    period = 12
    t = np.arange(n, dtype=np.float64)
    X = 0.5 * np.sin(2 * np.pi * t / period)
    S = fit_seasonal_dummies(X, period=period, n_harmonics=1)
    np.testing.assert_allclose(S, X, atol=1e-6)


def test_fit_seasonal_dummies_short_input_returns_zeros():
    X = np.array([1.0, 2.0])
    S = fit_seasonal_dummies(X, period=12, n_harmonics=3)
    np.testing.assert_array_equal(S, np.zeros(2))


def test_fit_trend_with_bp_no_break_for_pure_line():
    n = 200
    t = np.arange(n, dtype=np.float64)
    X = 0.5 + 0.01 * t
    trend, breaks = fit_trend_with_bp(X, h=0.15)
    assert breaks == []
    np.testing.assert_allclose(trend, X, atol=1e-9)


def test_fit_trend_with_bp_detects_step_in_clean_data():
    n = 200
    t = np.arange(n, dtype=np.float64)
    X = np.where(t < 100, 0.0, 1.0)
    _, breaks = fit_trend_with_bp(X, h=0.10)
    assert breaks
    assert min(abs(bp - 100) for bp in breaks) <= 3


def test_fit_trend_with_bp_rejects_t_length_mismatch():
    X = np.zeros(10)
    with pytest.raises(ValueError):
        fit_trend_with_bp(X, h=0.15, t=np.arange(5))


# ---------------------------------------------------------------------------
# Multivariate input rejection
# ---------------------------------------------------------------------------


def test_bfast_rejects_multivariate_input():
    X = np.zeros((100, 3))
    with pytest.raises(ValueError):
        fit_bfast(X, period=24)


def test_bfast_accepts_2d_single_column():
    X = _ndvi_with_break().reshape(-1, 1)
    blob = fit_bfast(X, period=24)
    assert blob.method == "BFAST"


# ---------------------------------------------------------------------------
# fit_metadata required keys
# ---------------------------------------------------------------------------


def test_bfast_fit_metadata_has_required_keys():
    X = _ndvi_with_break()
    blob = fit_bfast(X, period=24)
    for k in ("rmse", "rank", "n_params", "convergence", "version", "n_breakpoints", "iterations"):
        assert k in blob.fit_metadata, f"missing fit_metadata key: {k}"
    assert isinstance(blob.fit_metadata["convergence"], bool)


def test_bfast_n_breakpoints_matches_coefficients():
    X = _ndvi_with_break(bp=180, pre_level=0.5, post_level=0.2, noise_sd=0.02)
    blob = fit_bfast(X, period=24)
    assert blob.fit_metadata["n_breakpoints"] == len(blob.coefficients["break_epochs"])
