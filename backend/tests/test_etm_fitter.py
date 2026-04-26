"""Tests for the ETM (Extended Trajectory Model) fitter — SEG-013.

Reference: Bevis & Brown (2014), J. Geodesy 88:283-311, Eq. 1.
"""
from __future__ import annotations

import numpy as np

from app.services.decomposition.fitters.etm import build_etm_design_matrix, fit_etm
from app.models.decomposition import DecompositionBlob


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RNG = np.random.default_rng(42)


def _make_etm_signal(n: int = 500, noise_sigma: float = 0.0, seed: int = 0) -> tuple[np.ndarray, np.ndarray, dict]:
    """Build a synthetic ETM signal with known coefficients.

    Signal: 3 + 0.5·t + 2·H(t−50) + 1.2·log(1+(t−60)/20)
            + 0.5·sin(2πt/365.25) + 0.3·cos(2πt/365.25) + noise
    """
    t = np.arange(n, dtype=np.float64)
    X = (
        3.0
        + 0.5 * t
        + 2.0 * (t >= 50).astype(float)
        + 1.2 * np.log1p(np.maximum(0.0, (t - 60.0) / 20.0))
        + 0.5 * np.sin(2 * np.pi * t / 365.25)
        + 0.3 * np.cos(2 * np.pi * t / 365.25)
    )
    if noise_sigma > 0:
        rng = np.random.default_rng(seed)
        X = X + rng.normal(scale=noise_sigma, size=n)
    true_coeffs = {
        "x0": 3.0,
        "linear_rate": 0.5,
        "step_at_50": 2.0,
        "log_60_tau20": 1.2,
        "sin_365.25": 0.5,
        "cos_365.25": 0.3,
    }
    return X, t, true_coeffs


# ---------------------------------------------------------------------------
# Design matrix
# ---------------------------------------------------------------------------


def test_design_matrix_baseline_columns():
    """Without steps/transients/harmonics, only x0 and linear_rate."""
    t = np.arange(10, dtype=np.float64)
    A, labels = build_etm_design_matrix(t, known_steps=None, known_transients=None, harmonic_periods=[])
    assert labels == ["x0", "linear_rate"]
    assert A.shape == (10, 2)
    assert np.all(A[:, 0] == 1.0)
    assert np.allclose(A[:, 1], t)


def test_design_matrix_step_column():
    t = np.arange(20, dtype=np.float64)
    A, labels = build_etm_design_matrix(t, known_steps=[10.0], known_transients=None, harmonic_periods=[])
    assert "step_at_10" in labels
    col = A[:, labels.index("step_at_10")]
    assert np.all(col[:10] == 0.0)
    assert np.all(col[10:] == 1.0)


def test_design_matrix_log_transient():
    t = np.arange(30, dtype=np.float64)
    A, labels = build_etm_design_matrix(t, None, [(10.0, 5.0, "log")], harmonic_periods=[])
    assert "log_10_tau5" in labels
    col = A[:, labels.index("log_10_tau5")]
    assert col[0] == 0.0  # t < t_ref → max(0, ...) = 0 → log1p(0) = 0
    assert col[10] == 0.0  # exactly at t_ref → same
    assert col[20] > 0.0   # after t_ref


def test_design_matrix_exp_transient():
    t = np.arange(30, dtype=np.float64)
    A, labels = build_etm_design_matrix(t, None, [(10.0, 5.0, "exp")], harmonic_periods=[])
    assert "exp_10_tau5" in labels
    col = A[:, labels.index("exp_10_tau5")]
    # Before t_ref: exp(-0) = 1
    assert np.allclose(col[:10], 1.0)
    # After t_ref: decays
    assert col[20] < col[10]


def test_design_matrix_both_transient():
    t = np.arange(30, dtype=np.float64)
    A, labels = build_etm_design_matrix(t, None, [(10.0, 5.0, "both")], harmonic_periods=[])
    assert "log_10_tau5" in labels
    assert "exp_10_tau5" in labels


def test_design_matrix_harmonics():
    t = np.arange(100, dtype=np.float64)
    A, labels = build_etm_design_matrix(t, None, None, harmonic_periods=[365.25, 182.625])
    assert "sin_365.25" in labels
    assert "cos_365.25" in labels
    assert "sin_182.625" in labels
    assert "cos_182.625" in labels


def test_design_matrix_column_count():
    t = np.arange(50, dtype=np.float64)
    A, labels = build_etm_design_matrix(
        t,
        known_steps=[10.0, 30.0],
        known_transients=[(15.0, 5.0, "both")],
        harmonic_periods=[365.25],
    )
    # x0 + rate + 2 steps + 2 transients (log+exp) + 2 harmonics = 8
    assert A.shape == (50, 8)
    assert len(labels) == 8


# ---------------------------------------------------------------------------
# Coefficient recovery — Bevis-Brown Eq. 1
# ---------------------------------------------------------------------------


def test_noise_free_perfect_recovery():
    """RMSE < 1e-6 on a noise-free ETM signal."""
    X, t, _ = _make_etm_signal(n=500, noise_sigma=0.0)
    blob = fit_etm(
        X, t,
        known_steps=[50.0],
        known_transients=[(60.0, 20.0, "log")],
        harmonic_periods=[365.25],
    )
    assert blob.fit_metadata["rmse"] < 1e-6


def test_coefficient_names_bevis_brown():
    """Coefficient names follow Bevis-Brown Eq. 1 naming convention."""
    X, t, _ = _make_etm_signal(n=500, noise_sigma=0.0)
    blob = fit_etm(
        X, t,
        known_steps=[50.0],
        known_transients=[(60.0, 20.0, "log")],
        harmonic_periods=[365.25],
    )
    assert "x0" in blob.coefficients
    assert "linear_rate" in blob.coefficients
    assert "step_at_50" in blob.coefficients
    assert "log_60_tau20" in blob.coefficients
    assert "sin_365.25" in blob.coefficients
    assert "cos_365.25" in blob.coefficients


def test_noisy_coefficient_recovery_within_5_percent():
    """Coefficients recovered within 5 % of true values (noise sigma=0.05).

    Bevis & Brown (2014) Eq. 1 — linear + step + log-transient + annual harmonic.
    """
    X, t, true = _make_etm_signal(n=500, noise_sigma=0.05, seed=7)
    blob = fit_etm(
        X, t,
        known_steps=[50.0],
        known_transients=[(60.0, 20.0, "log")],
        harmonic_periods=[365.25],
    )
    for key, true_val in true.items():
        # Map true key → blob coefficient key
        blob_key = key
        got = blob.coefficients.get(blob_key)
        assert got is not None, f"Missing coefficient: {blob_key}"
        assert abs(got - true_val) <= 0.05 * abs(true_val) + 1e-3, (
            f"{blob_key}: expected ~{true_val:.4f}, got {got:.4f}"
        )


# ---------------------------------------------------------------------------
# Reassembly — sum of components equals original X
# ---------------------------------------------------------------------------


def test_reassembly_noise_free():
    X, t, _ = _make_etm_signal(n=200, noise_sigma=0.0)
    blob = fit_etm(X, t, known_steps=[50.0], known_transients=[(60.0, 20.0, "log")], harmonic_periods=[365.25])
    assert np.allclose(blob.reassemble(), X, rtol=1e-10, atol=1e-10)


def test_reassembly_noisy():
    X, t, _ = _make_etm_signal(n=200, noise_sigma=0.1)
    blob = fit_etm(X, t, known_steps=[50.0], harmonic_periods=[365.25])
    assert np.allclose(blob.reassemble(), X, rtol=1e-8, atol=1e-8)


def test_reassembly_no_optional_terms():
    """Default call: t = arange(n), no steps/transients, default harmonics."""
    rng = np.random.default_rng(10)
    X = rng.normal(size=100)
    blob = fit_etm(X)
    assert np.allclose(blob.reassemble(), X, rtol=1e-8, atol=1e-8)


# ---------------------------------------------------------------------------
# Residual storage
# ---------------------------------------------------------------------------


def test_residual_stored_in_blob():
    """blob.residual must not be None; Tier-2 ops (add_uncertainty) read it."""
    X, t, _ = _make_etm_signal(n=100, noise_sigma=0.1)
    blob = fit_etm(X, t, harmonic_periods=[365.25])
    assert blob.residual is not None
    assert blob.residual.shape == X.shape


def test_residual_in_components():
    """blob.components['residual'] must equal blob.residual."""
    X = np.random.default_rng(3).normal(size=80)
    blob = fit_etm(X, harmonic_periods=[])
    assert "residual" in blob.components
    assert np.array_equal(blob.components["residual"], blob.residual)


def test_residual_equals_x_minus_fitted():
    """Residual = X - fitted; fitted = sum of all non-residual components."""
    X = np.linspace(0, 5, 120) + 0.01 * np.random.default_rng(1).normal(size=120)
    blob = fit_etm(X, harmonic_periods=[])
    fitted = sum(v for k, v in blob.components.items() if k != "residual")
    assert np.allclose(blob.residual, X - fitted, atol=1e-10)


# ---------------------------------------------------------------------------
# Harmonic periods — configurable
# ---------------------------------------------------------------------------


def test_harmonic_periods_configurable():
    X = np.random.default_rng(5).normal(size=200)
    blob = fit_etm(X, harmonic_periods=[100.0, 50.0])
    assert "sin_100" in blob.coefficients
    assert "cos_100" in blob.coefficients
    assert "sin_50" in blob.coefficients
    assert "cos_50" in blob.coefficients


def test_no_harmonics():
    X = np.random.default_rng(6).normal(size=50)
    blob = fit_etm(X, harmonic_periods=[])
    assert not any(k.startswith("sin_") or k.startswith("cos_") for k in blob.coefficients)


# ---------------------------------------------------------------------------
# fit_metadata
# ---------------------------------------------------------------------------


def test_fit_metadata_fields():
    X = np.random.default_rng(9).normal(size=60)
    blob = fit_etm(X)
    meta = blob.fit_metadata
    assert "rmse" in meta
    assert "rank" in meta
    assert "n_params" in meta
    assert "convergence" in meta
    assert isinstance(meta["rmse"], float)
    assert isinstance(meta["rank"], int)
    assert isinstance(meta["n_params"], int)


def test_fit_metadata_n_params_matches_design():
    """n_params == number of columns in the design matrix."""
    X = np.random.default_rng(11).normal(size=100)
    blob = fit_etm(
        X,
        known_steps=[30.0],
        known_transients=[(40.0, 10.0, "both")],
        harmonic_periods=[365.25],
    )
    # x0 + rate + 1 step + 2 transients + 2 harmonics = 7
    assert blob.fit_metadata["n_params"] == 7


# ---------------------------------------------------------------------------
# Under-determined (too few samples)
# ---------------------------------------------------------------------------


def test_underdetermined_returns_blob():
    """n < p: graceful fallback to constant model; returns a valid DecompositionBlob."""
    X = np.array([1.0, 2.0, 3.0])  # n=3; with default harmonics p=6 → underdetermined
    blob = fit_etm(X, harmonic_periods=[365.25, 182.625])
    assert isinstance(blob, DecompositionBlob)
    assert blob.method == "ETM"
    assert blob.fit_metadata.get("underdetermined") is True


def test_underdetermined_reassembles():
    X = np.array([2.0, 4.0, 6.0])
    blob = fit_etm(X, harmonic_periods=[365.25, 182.625])
    assert np.allclose(blob.reassemble(), X, rtol=1e-6, atol=1e-6)


# ---------------------------------------------------------------------------
# Multivariate input
# ---------------------------------------------------------------------------


def test_multivariate_shape():
    X = np.random.default_rng(20).normal(size=(80, 3))
    blob = fit_etm(X, harmonic_periods=[])
    for name, arr in blob.components.items():
        assert arr.shape == (80, 3), f"component {name} has wrong shape"


def test_multivariate_reassembly():
    X = np.random.default_rng(21).normal(size=(60, 2))
    blob = fit_etm(X, harmonic_periods=[])
    assert np.allclose(blob.reassemble(), X, rtol=1e-8, atol=1e-8)


def test_multivariate_residual_shape():
    X = np.random.default_rng(22).normal(size=(50, 4))
    blob = fit_etm(X, harmonic_periods=[])
    assert blob.residual is not None
    assert blob.residual.shape == (50, 4)


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------


def test_json_roundtrip():
    X, t, _ = _make_etm_signal(n=100, noise_sigma=0.05)
    blob = fit_etm(X, t, known_steps=[50.0], known_transients=[(60.0, 20.0, "log")], harmonic_periods=[365.25])
    blob2 = DecompositionBlob.from_json(blob.to_json())
    for key in blob.components:
        assert np.allclose(blob.components[key], blob2.components[key], rtol=1e-12), key
    assert blob.method == blob2.method == "ETM"


# ---------------------------------------------------------------------------
# Dispatch integration
# ---------------------------------------------------------------------------


def test_dispatch_to_etm_for_trend():
    from app.services.decomposition.dispatcher import dispatch_fitter, FITTER_REGISTRY
    fn = dispatch_fitter("trend")
    assert fn is FITTER_REGISTRY["ETM"]


def test_dispatch_to_etm_for_step():
    from app.services.decomposition.dispatcher import dispatch_fitter, FITTER_REGISTRY
    fn = dispatch_fitter("step")
    assert fn is FITTER_REGISTRY["ETM"]


def test_dispatch_to_etm_for_transient():
    from app.services.decomposition.dispatcher import dispatch_fitter, FITTER_REGISTRY
    fn = dispatch_fitter("transient")
    assert fn is FITTER_REGISTRY["ETM"]
