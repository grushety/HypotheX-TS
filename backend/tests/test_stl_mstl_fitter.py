"""Tests for the STL / MSTL decomposition fitters — SEG-014.

References
----------
Cleveland et al. (1990) J. Official Statistics 6(1):3–73.
Bandara, Hyndman & Bergmeir (2021) arXiv 2107.13462.
"""
from __future__ import annotations

import numpy as np

from app.services.decomposition.fitters.stl import detect_dominant_period, fit_stl
from app.services.decomposition.fitters.mstl import fit_mstl
from app.models.decomposition import DecompositionBlob


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RNG = np.random.default_rng(42)


def _sine(period: float, n: int) -> np.ndarray:
    return np.sin(2 * np.pi * np.arange(n, dtype=float) / period)


# ---------------------------------------------------------------------------
# detect_dominant_period
# ---------------------------------------------------------------------------


def test_detect_dominant_period_single_returns_int():
    """Pure sin(2πt/12) on n=120 — only one dominant period."""
    X = _sine(12, 120)
    detected = detect_dominant_period(X)
    assert isinstance(detected, int), f"Expected int, got {type(detected)}"
    assert detected == 12


def test_detect_dominant_period_multi_returns_list():
    """Two equal-amplitude sinusoids; n=504 = LCM(24,168)*3 for exact FFT bins."""
    t = np.arange(504, dtype=float)
    X = _sine(24, 504) + _sine(168, 504)
    detected = detect_dominant_period(X)
    assert isinstance(detected, list), f"Expected list, got {type(detected)}"
    assert 24 in detected, f"24 not in {detected}"
    assert 168 in detected, f"168 not in {detected}"


def test_detect_dominant_period_multi_sorted_ascending():
    t = np.arange(504, dtype=float)
    X = _sine(24, 504) + _sine(168, 504)
    detected = detect_dominant_period(X)
    assert detected == sorted(detected)


def test_detect_dominant_period_with_noise():
    """Period 12 survives mild Gaussian noise (σ=0.1)."""
    X = _sine(12, 240) + 0.1 * RNG.normal(size=240)
    detected = detect_dominant_period(X)
    result = detected if isinstance(detected, int) else detected[0]
    assert abs(result - 12) <= 1, f"Expected ~12, got {result}"


def test_detect_dominant_period_too_short_fallback():
    """Fewer than 2*min_period samples → falls back to min_period."""
    X = np.array([1.0, 2.0])
    detected = detect_dominant_period(X, min_period=4)
    assert detected == 4


# ---------------------------------------------------------------------------
# fit_stl — design and coefficients
# ---------------------------------------------------------------------------


def test_stl_method_name():
    X = _sine(12, 120)
    blob = fit_stl(X, period=12)
    assert blob.method == "STL"


def test_stl_components_present():
    X = _sine(12, 120)
    blob = fit_stl(X, period=12)
    assert "trend" in blob.components
    assert "seasonal" in blob.components
    assert "residual" in blob.components


def test_stl_components_shapes():
    n = 120
    X = _sine(12, n)
    blob = fit_stl(X, period=12)
    for name, arr in blob.components.items():
        assert arr.shape == (n,), f"{name} has shape {arr.shape}"


def test_stl_robust_flag_true():
    X = _sine(12, 120)
    blob = fit_stl(X, period=12, robust=True)
    assert blob.fit_metadata["robust"] is True


def test_stl_robust_flag_false():
    X = _sine(12, 120)
    blob = fit_stl(X, period=12, robust=False)
    assert blob.fit_metadata["robust"] is False


# ---------------------------------------------------------------------------
# fit_stl — reassembly (Cleveland 1990: R(t) = X − T − S by construction)
# ---------------------------------------------------------------------------


def test_stl_reassembly_noisefree():
    """STL is exact: trend + seasonal + residual = X up to float rounding."""
    X = _sine(12, 120) + 0.5 * np.linspace(0, 3, 120)
    blob = fit_stl(X, period=12)
    assert np.allclose(blob.reassemble(), X, rtol=1e-10, atol=1e-10)


def test_stl_reassembly_noisy():
    X = _sine(12, 120) + 0.2 * RNG.normal(size=120)
    blob = fit_stl(X, period=12)
    assert np.allclose(blob.reassemble(), X, rtol=1e-10, atol=1e-10)


def test_stl_residual_stored():
    """blob.residual must match blob.components['residual']."""
    X = _sine(12, 120) + 0.1 * RNG.normal(size=120)
    blob = fit_stl(X, period=12)
    assert blob.residual is not None
    assert blob.residual.shape == X.shape
    assert np.array_equal(blob.residual, blob.components["residual"])


def test_stl_residual_equals_x_minus_fitted():
    X = _sine(12, 120) + 0.05 * RNG.normal(size=120)
    blob = fit_stl(X, period=12)
    fitted = blob.components["trend"] + blob.components["seasonal"]
    assert np.allclose(blob.residual, X - fitted, atol=1e-12)


# ---------------------------------------------------------------------------
# fit_stl — auto period detection
# ---------------------------------------------------------------------------


def test_stl_auto_detect_single_period():
    """Auto-detect mode: dominant period 12 recovered, reassembly holds."""
    X = _sine(12, 120)
    blob = fit_stl(X)  # period=None
    assert blob.method == "STL"
    assert np.allclose(blob.reassemble(), X, rtol=1e-10, atol=1e-10)


# ---------------------------------------------------------------------------
# fit_stl — fit_metadata
# ---------------------------------------------------------------------------


def test_stl_fit_metadata_fields():
    X = _sine(12, 120)
    blob = fit_stl(X, period=12)
    meta = blob.fit_metadata
    assert "rmse" in meta
    assert "rank" in meta
    assert "n_params" in meta
    assert "convergence" in meta
    assert isinstance(meta["rmse"], float)
    assert isinstance(meta["rank"], int)
    assert isinstance(meta["n_params"], int)
    assert meta["convergence"] is True


def test_stl_fit_metadata_n_params():
    X = _sine(12, 120)
    blob = fit_stl(X, period=12)
    assert blob.fit_metadata["n_params"] == 12 + 2


# ---------------------------------------------------------------------------
# fit_stl — multivariate input
# ---------------------------------------------------------------------------


def test_stl_multivariate_shapes():
    n, d = 120, 3
    X = np.column_stack([_sine(12, n) + 0.1 * RNG.normal(size=n) for _ in range(d)])
    blob = fit_stl(X, period=12)
    for name, arr in blob.components.items():
        assert arr.shape == (n, d), f"{name} has shape {arr.shape}"


def test_stl_multivariate_reassembly():
    n, d = 120, 2
    X = np.column_stack([_sine(12, n) + 0.05 * RNG.normal(size=n) for _ in range(d)])
    blob = fit_stl(X, period=12)
    assert np.allclose(blob.reassemble(), X, rtol=1e-10, atol=1e-10)


def test_stl_multivariate_residual_shape():
    n, d = 120, 4
    X = np.column_stack([_sine(12, n) for _ in range(d)])
    blob = fit_stl(X, period=12)
    assert blob.residual is not None
    assert blob.residual.shape == (n, d)


# ---------------------------------------------------------------------------
# fit_stl — JSON round-trip
# ---------------------------------------------------------------------------


def test_stl_json_roundtrip():
    X = _sine(12, 120) + 0.05 * RNG.normal(size=120)
    blob = fit_stl(X, period=12)
    blob2 = DecompositionBlob.from_json(blob.to_json())
    for key in blob.components:
        assert np.allclose(blob.components[key], blob2.components[key], rtol=1e-12), key
    assert blob.method == blob2.method == "STL"


# ---------------------------------------------------------------------------
# fit_mstl — design and components
# ---------------------------------------------------------------------------


def test_mstl_method_name():
    t = np.arange(360, dtype=float)
    X = _sine(12, 360) + _sine(60, 360)
    blob = fit_mstl(X, periods=[12, 60])
    assert blob.method == "MSTL"


def test_mstl_seasonal_component_names():
    """Named components follow 'seasonal_{T}' convention (Bandara 2021)."""
    t = np.arange(360, dtype=float)
    X = _sine(12, 360) + _sine(60, 360)
    blob = fit_mstl(X, periods=[12, 60])
    assert "trend" in blob.components
    assert "seasonal_12" in blob.components
    assert "seasonal_60" in blob.components
    assert "residual" in blob.components


def test_mstl_reassembly_noisefree():
    """MSTL is exact: components sum to X within float rounding."""
    t = np.arange(360, dtype=float)
    X = _sine(12, 360) + _sine(60, 360)
    blob = fit_mstl(X, periods=[12, 60])
    assert np.allclose(blob.reassemble(), X, rtol=1e-10, atol=1e-10)


def test_mstl_reassembly_noisy():
    t = np.arange(360, dtype=float)
    X = _sine(12, 360) + _sine(60, 360) + 0.1 * RNG.normal(size=360)
    blob = fit_mstl(X, periods=[12, 60])
    assert np.allclose(blob.reassemble(), X, rtol=1e-10, atol=1e-10)


def test_mstl_residual_stored():
    t = np.arange(360, dtype=float)
    X = _sine(12, 360) + _sine(60, 360)
    blob = fit_mstl(X, periods=[12, 60])
    assert blob.residual is not None
    assert blob.residual.shape == X.shape
    assert np.array_equal(blob.residual, blob.components["residual"])


def test_mstl_fit_metadata_fields():
    t = np.arange(360, dtype=float)
    X = _sine(12, 360) + _sine(60, 360)
    blob = fit_mstl(X, periods=[12, 60])
    meta = blob.fit_metadata
    assert "rmse" in meta
    assert "rank" in meta
    assert "n_params" in meta
    assert "convergence" in meta
    assert isinstance(meta["rmse"], float)
    assert meta["convergence"] is True


# ---------------------------------------------------------------------------
# fit_mstl — auto period detection (daily + weekly)
# ---------------------------------------------------------------------------


def test_mstl_auto_detect_periods_daily_weekly():
    """Auto-detect on sin(2πt/24) + sin(2πt/168); n=504=LCM(24,168)*3.

    Both periods must appear as 'seasonal_{T}' components and the blob
    must reassemble exactly.
    """
    t = np.arange(504, dtype=float)
    X = _sine(24, 504) + _sine(168, 504)
    blob = fit_mstl(X)  # periods=None → auto-detect
    assert "seasonal_24" in blob.components, list(blob.components)
    assert "seasonal_168" in blob.components, list(blob.components)
    assert np.allclose(blob.reassemble(), X, rtol=1e-10, atol=1e-10)


# ---------------------------------------------------------------------------
# fit_mstl — multivariate input
# ---------------------------------------------------------------------------


def test_mstl_multivariate_shapes():
    n, d = 360, 2
    base = _sine(12, n) + _sine(60, n)
    X = np.column_stack([base + 0.05 * RNG.normal(size=n) for _ in range(d)])
    blob = fit_mstl(X, periods=[12, 60])
    for name, arr in blob.components.items():
        assert arr.shape == (n, d), f"{name} has shape {arr.shape}"


def test_mstl_multivariate_reassembly():
    n, d = 360, 2
    base = _sine(12, n) + _sine(60, n)
    X = np.column_stack([base + 0.05 * RNG.normal(size=n) for _ in range(d)])
    blob = fit_mstl(X, periods=[12, 60])
    assert np.allclose(blob.reassemble(), X, rtol=1e-10, atol=1e-10)


def test_mstl_multivariate_residual_shape():
    n, d = 360, 3
    X = np.column_stack([_sine(12, n) + _sine(60, n) for _ in range(d)])
    blob = fit_mstl(X, periods=[12, 60])
    assert blob.residual is not None
    assert blob.residual.shape == (n, d)


# ---------------------------------------------------------------------------
# fit_mstl — JSON round-trip
# ---------------------------------------------------------------------------


def test_mstl_json_roundtrip():
    t = np.arange(360, dtype=float)
    X = _sine(12, 360) + _sine(60, 360) + 0.05 * RNG.normal(size=360)
    blob = fit_mstl(X, periods=[12, 60])
    blob2 = DecompositionBlob.from_json(blob.to_json())
    for key in blob.components:
        assert np.allclose(blob.components[key], blob2.components[key], rtol=1e-12), key
    assert blob.method == blob2.method == "MSTL"


# ---------------------------------------------------------------------------
# fit_mstl — unsorted period input (regression: column mislabeling fix)
# ---------------------------------------------------------------------------


def test_mstl_unsorted_periods_labels_are_correct():
    """Passing periods=[60, 12] must still label columns as seasonal_12 and seasonal_60.

    statsmodels MSTL sorts periods internally; fit_mstl must sort valid_periods
    to the same order before naming columns.
    """
    t = np.arange(360, dtype=float)
    X = _sine(12, 360) + 2 * _sine(60, 360)
    blob_sorted = fit_mstl(X, periods=[12, 60])
    blob_unsorted = fit_mstl(X, periods=[60, 12])

    assert "seasonal_12" in blob_unsorted.components
    assert "seasonal_60" in blob_unsorted.components
    # The actual seasonal arrays should be the same regardless of input order
    assert np.allclose(blob_sorted.components["seasonal_12"], blob_unsorted.components["seasonal_12"], atol=1e-10)
    assert np.allclose(blob_sorted.components["seasonal_60"], blob_unsorted.components["seasonal_60"], atol=1e-10)


def test_mstl_underdetermined_returns_blob():
    """n=4, period=2: 2*2=4 not < 4 → no valid periods → flat fallback."""
    X = np.array([1.0, 2.0, 3.0, 4.0])
    blob = fit_mstl(X, periods=[2])
    assert isinstance(blob, DecompositionBlob)
    assert blob.method == "MSTL"
    assert blob.fit_metadata.get("underdetermined") is True


def test_mstl_underdetermined_reassembles():
    X = np.array([2.0, 4.0, 6.0, 8.0])
    blob = fit_mstl(X, periods=[2])
    assert np.allclose(blob.reassemble(), X, rtol=1e-6, atol=1e-6)


# ---------------------------------------------------------------------------
# Dispatch integration
# ---------------------------------------------------------------------------


def test_dispatch_cycle_to_stl():
    from app.services.decomposition.dispatcher import dispatch_fitter, FITTER_REGISTRY
    fn = dispatch_fitter("cycle")
    assert fn is FITTER_REGISTRY["STL"]


def test_dispatch_cycle_multi_period_to_mstl():
    from app.services.decomposition.dispatcher import dispatch_fitter, FITTER_REGISTRY
    fn = dispatch_fitter("cycle", "multi-period")
    assert fn is FITTER_REGISTRY["MSTL"]
