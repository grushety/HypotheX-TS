"""Tests for the Eckhardt baseflow fitter — SEG-016.

References
----------
Eckhardt, K. (2005) Hydrological Processes 19(2):507–515.
Lyne, V. & Hollick, M. (1979) I.E. Aust. Natl. Conf. Publ. 79/10.
Tallaksen, L.M. (1995) J. Hydrology 165:349–370.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.decomposition.dispatcher import FITTER_REGISTRY, _ensure_fitters_loaded
from app.services.decomposition.fitters.eckhardt import (
    DEFAULT_A,
    DEFAULT_BFI_MAX,
    calibrate_eckhardt,
    eckhardt_baseflow,
    estimate_long_term_bfi,
    estimate_recession_constant,
)


RNG = np.random.default_rng(42)


# ---------------------------------------------------------------------------
# Synthetic hydrograph fixture
# ---------------------------------------------------------------------------


def _storm_pulse_hydrograph(
    n: int = 200,
    base: float = 2.0,
    peak: float = 10.0,
    storm_start: int = 50,
    rise_len: int = 5,
    decay_tau: float = 8.0,
) -> np.ndarray:
    """Constant baseflow + single storm pulse with exponential recession.

    The pulse rises linearly from ``base`` to ``peak`` over ``rise_len``
    samples starting at ``storm_start``, then decays exponentially with
    time-constant ``decay_tau`` back to ``base``.
    """
    Q = np.full(n, float(base), dtype=np.float64)
    rise_end = storm_start + rise_len
    if rise_end < n:
        Q[storm_start:rise_end] = np.linspace(base, peak, rise_len)
        decay_t = np.arange(n - rise_end, dtype=np.float64)
        Q[rise_end:] = base + (peak - base) * np.exp(-decay_t / decay_tau)
    return Q


# ---------------------------------------------------------------------------
# Registry / dispatcher integration
# ---------------------------------------------------------------------------


def test_eckhardt_registered():
    _ensure_fitters_loaded()
    assert "Eckhardt" in FITTER_REGISTRY
    assert FITTER_REGISTRY["Eckhardt"] is eckhardt_baseflow


def test_eckhardt_returns_decomposition_blob():
    Q = _storm_pulse_hydrograph()
    blob = eckhardt_baseflow(Q)
    assert isinstance(blob, DecompositionBlob)
    assert blob.method == "Eckhardt"


# ---------------------------------------------------------------------------
# Component shape and naming
# ---------------------------------------------------------------------------


def test_eckhardt_components_present():
    Q = _storm_pulse_hydrograph()
    blob = eckhardt_baseflow(Q)
    assert "baseflow" in blob.components
    assert "quickflow" in blob.components
    assert "residual" in blob.components


def test_eckhardt_components_have_correct_shape():
    n = 300
    Q = _storm_pulse_hydrograph(n=n)
    blob = eckhardt_baseflow(Q)
    for name, arr in blob.components.items():
        assert arr.shape == (n,), f"{name} has shape {arr.shape}"


# ---------------------------------------------------------------------------
# Exact split (Q = b + quickflow; residual all zeros)
# ---------------------------------------------------------------------------


def test_eckhardt_residual_is_exactly_zero():
    Q = _storm_pulse_hydrograph()
    blob = eckhardt_baseflow(Q)
    np.testing.assert_array_equal(blob.components["residual"], np.zeros_like(Q))
    np.testing.assert_array_equal(blob.residual, np.zeros_like(Q))


def test_eckhardt_baseflow_plus_quickflow_equals_input():
    Q = _storm_pulse_hydrograph()
    blob = eckhardt_baseflow(Q)
    np.testing.assert_allclose(
        blob.components["baseflow"] + blob.components["quickflow"], Q, atol=1e-12
    )


# ---------------------------------------------------------------------------
# Physical constraint b(t) ≤ Q(t) (Eckhardt §2)
# ---------------------------------------------------------------------------


def test_eckhardt_baseflow_never_exceeds_streamflow():
    Q = _storm_pulse_hydrograph()
    blob = eckhardt_baseflow(Q)
    assert (blob.components["baseflow"] <= Q + 1e-12).all()


def test_eckhardt_quickflow_is_non_negative():
    Q = _storm_pulse_hydrograph()
    blob = eckhardt_baseflow(Q)
    assert (blob.components["quickflow"] >= -1e-12).all()


# ---------------------------------------------------------------------------
# Initial condition
# ---------------------------------------------------------------------------


def test_eckhardt_initial_baseflow_equals_q0_times_bfimax():
    Q = _storm_pulse_hydrograph()
    bfi_max = 0.7
    blob = eckhardt_baseflow(Q, bfi_max=bfi_max, a=0.95)
    assert blob.components["baseflow"][0] == pytest.approx(Q[0] * bfi_max)


# ---------------------------------------------------------------------------
# Bit-identical Eckhardt 2005 Eq. 6
# ---------------------------------------------------------------------------


def _reference_eckhardt(Q: np.ndarray, bfi_max: float, a: float) -> np.ndarray:
    """Verbatim Eckhardt (2005) Eq. 6 — used to guard against drift in the
    fitter implementation.
    """
    n = len(Q)
    b = np.zeros(n, dtype=np.float64)
    if n == 0:
        return b
    b[0] = float(Q[0]) * float(bfi_max)
    denom = 1.0 - float(a) * float(bfi_max)
    for t in range(1, n):
        raw = (
            (1.0 - float(bfi_max)) * float(a) * b[t - 1]
            + (1.0 - float(a)) * float(bfi_max) * float(Q[t])
        ) / denom
        b[t] = min(raw, float(Q[t]))
    return b


def test_eckhardt_matches_paper_equation_6_bit_identical():
    Q = _storm_pulse_hydrograph()
    bfi_max, a = 0.8, 0.98
    blob = eckhardt_baseflow(Q, bfi_max=bfi_max, a=a)
    ref = _reference_eckhardt(Q, bfi_max=bfi_max, a=a)
    np.testing.assert_array_equal(blob.components["baseflow"], ref)


def test_eckhardt_matches_paper_equation_6_for_alternative_parameters():
    """Cover the BFImax/a corners used elsewhere in Eckhardt 2005 Table 1."""
    Q = _storm_pulse_hydrograph()
    for bfi_max, a in [(0.5, 0.925), (0.25, 0.95), (0.7, 0.99)]:
        blob = eckhardt_baseflow(Q, bfi_max=bfi_max, a=a)
        ref = _reference_eckhardt(Q, bfi_max=bfi_max, a=a)
        np.testing.assert_array_equal(blob.components["baseflow"], ref)


# ---------------------------------------------------------------------------
# Constant flow → baseflow tracks Q
# ---------------------------------------------------------------------------


def test_eckhardt_constant_flow_baseflow_converges_to_bfimax_times_q():
    """Steady-state of Eckhardt 2005 Eq. 6 is b_ss = BFImax · Q (algebraically).

    Solving b = ((1−BFI)·a·b + (1−a)·BFI·Q)/(1−a·BFI) → b·(1−a) = (1−a)·BFI·Q
    → b = BFI·Q.  The b ≤ Q clamp is inactive once Q is held constant.
    """
    Q = np.full(500, 5.0, dtype=np.float64)
    bfi_max, a = 0.8, 0.98
    blob = eckhardt_baseflow(Q, bfi_max=bfi_max, a=a)
    expected = bfi_max * 5.0
    np.testing.assert_allclose(blob.components["baseflow"][-50:], expected, atol=1e-3)
    np.testing.assert_allclose(
        blob.components["quickflow"][-50:], 5.0 - expected, atol=1e-3
    )


def test_eckhardt_constant_flow_with_high_bfimax_recovers_q():
    """BFImax → 1 collapses baseflow onto Q (no quickflow, fully gauged base)."""
    Q = np.full(500, 5.0, dtype=np.float64)
    blob = eckhardt_baseflow(Q, bfi_max=0.99, a=0.98)
    np.testing.assert_allclose(blob.components["baseflow"][-50:], 4.95, atol=1e-3)


# ---------------------------------------------------------------------------
# Storm event recovery (AC: peak=10, base=2, recover to 5 % after transient)
# ---------------------------------------------------------------------------


def test_eckhardt_baseflow_stays_below_peak_during_storm():
    Q = _storm_pulse_hydrograph(n=300, base=2.0, peak=10.0, storm_start=50)
    blob = eckhardt_baseflow(Q, bfi_max=0.8, a=0.98)
    storm_window = blob.components["baseflow"][50:80]
    assert storm_window.max() < 10.0, "baseflow should stay below peak"


def test_eckhardt_baseflow_recovers_within_5_percent_after_storm():
    """AC fixture: known b=2, peak=10 → baseflow recovers to within 5 % of the
    underlying base after the storm.  Using BFImax ≈ 1 since the synthetic
    signal's true long-term BFI is close to unity (a brief storm on top of a
    constant baseflow has BFI very close to 1).
    """
    Q = _storm_pulse_hydrograph(
        n=400, base=2.0, peak=10.0, storm_start=50, rise_len=5, decay_tau=8.0
    )
    blob = eckhardt_baseflow(Q, bfi_max=0.99, a=0.98)
    tail = blob.components["baseflow"][-50:]
    assert np.all(np.abs(tail - 2.0) <= 0.05 * 2.0), (
        f"baseflow tail = {tail.mean():.4f}, expected 2.0 ± 5 %"
    )


# ---------------------------------------------------------------------------
# Coefficients exposed for OP-020 raise_lower / OP-032 enforce_conservation
# ---------------------------------------------------------------------------


def test_eckhardt_coefficients_have_expected_keys():
    Q = _storm_pulse_hydrograph()
    blob = eckhardt_baseflow(Q, bfi_max=0.8, a=0.98)
    assert blob.coefficients["BFImax"] == pytest.approx(0.8)
    assert blob.coefficients["a"] == pytest.approx(0.98)


def test_eckhardt_coefficients_are_python_floats():
    Q = _storm_pulse_hydrograph()
    blob = eckhardt_baseflow(Q)
    assert isinstance(blob.coefficients["BFImax"], float)
    assert isinstance(blob.coefficients["a"], float)


def test_eckhardt_fit_metadata_has_required_keys():
    Q = _storm_pulse_hydrograph()
    blob = eckhardt_baseflow(Q)
    for k in ("rmse", "rank", "n_params", "convergence", "version", "bfi"):
        assert k in blob.fit_metadata, f"missing fit_metadata key: {k}"
    assert blob.fit_metadata["rmse"] == 0.0
    assert blob.fit_metadata["convergence"] is True


def test_eckhardt_metadata_bfi_is_total_baseflow_over_total_flow():
    Q = _storm_pulse_hydrograph()
    blob = eckhardt_baseflow(Q)
    expected = float(np.sum(blob.components["baseflow"]) / np.sum(Q))
    assert blob.fit_metadata["bfi"] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_eckhardt_rejects_negative_streamflow():
    Q = np.array([1.0, -0.5, 1.0])
    with pytest.raises(ValueError, match="non-negative"):
        eckhardt_baseflow(Q)


def test_eckhardt_zero_flow_is_allowed():
    """A dry channel (Q ≡ 0) is physically valid; baseflow ≡ 0."""
    Q = np.zeros(50, dtype=np.float64)
    blob = eckhardt_baseflow(Q)
    np.testing.assert_array_equal(blob.components["baseflow"], 0.0)
    np.testing.assert_array_equal(blob.components["quickflow"], 0.0)
    assert blob.fit_metadata["bfi"] == 0.0


def test_eckhardt_rejects_a_out_of_unit_interval():
    Q = _storm_pulse_hydrograph()
    with pytest.raises(ValueError, match="recession constant"):
        eckhardt_baseflow(Q, a=0.0)
    with pytest.raises(ValueError, match="recession constant"):
        eckhardt_baseflow(Q, a=1.0)


def test_eckhardt_rejects_bfimax_out_of_unit_interval():
    Q = _storm_pulse_hydrograph()
    with pytest.raises(ValueError, match="BFImax"):
        eckhardt_baseflow(Q, bfi_max=0.0)
    with pytest.raises(ValueError, match="BFImax"):
        eckhardt_baseflow(Q, bfi_max=1.0)


def test_eckhardt_rejects_multivariate_input():
    Q = np.zeros((100, 3))
    with pytest.raises(ValueError, match="1-D"):
        eckhardt_baseflow(Q)


def test_eckhardt_accepts_2d_single_column():
    Q = _storm_pulse_hydrograph().reshape(-1, 1)
    blob = eckhardt_baseflow(Q)
    assert blob.method == "Eckhardt"


# ---------------------------------------------------------------------------
# Calibration helpers
# ---------------------------------------------------------------------------


def test_estimate_recession_constant_recovers_known_a():
    """Pure exponential recession Q(t)=Q0·a^t → a = exp(mean(log ratios))."""
    n = 100
    a_true = 0.95
    Q = 10.0 * (a_true ** np.arange(n, dtype=np.float64))
    a_est = estimate_recession_constant(Q, recession_segments=[(0, n)])
    assert abs(a_est - a_true) < 1e-6


def test_estimate_recession_constant_clips_to_valid_range():
    Q = np.array([10.0, 1.0, 0.1])  # decay too fast → a < 0.5 lower bound
    a_est = estimate_recession_constant(Q, recession_segments=[(0, 3)])
    assert 0.5 <= a_est <= 0.999


def test_estimate_recession_constant_falls_back_when_no_data():
    Q = np.array([1.0, 2.0, 3.0])
    a_est = estimate_recession_constant(Q, recession_segments=[])
    assert a_est == DEFAULT_A


def test_estimate_recession_constant_skips_zero_values():
    """Zero or negative samples must not produce log(0) NaNs."""
    Q = np.array([5.0, 0.0, 4.5, 4.0])
    a_est = estimate_recession_constant(Q, recession_segments=[(0, 4)])
    assert 0.5 <= a_est <= 0.999


def test_estimate_long_term_bfi_returns_fraction_of_total():
    Q = _storm_pulse_hydrograph()
    bfi = estimate_long_term_bfi(Q, a=0.95)
    assert 0.05 <= bfi <= 0.95


def test_estimate_long_term_bfi_handles_empty_input():
    bfi = estimate_long_term_bfi(np.array([], dtype=np.float64), a=0.95)
    assert bfi == DEFAULT_BFI_MAX


def test_calibrate_eckhardt_returns_clipped_pair():
    Q = _storm_pulse_hydrograph(n=400, base=2.0, peak=10.0)
    a_cal, bfi_max_cal = calibrate_eckhardt(Q, recession_segments=[(60, 200)])
    assert 0.5 <= a_cal <= 0.999
    assert 0.05 <= bfi_max_cal <= 0.95


def test_calibrate_eckhardt_results_are_usable_by_fitter():
    Q = _storm_pulse_hydrograph(n=400, base=2.0, peak=10.0)
    a_cal, bfi_max_cal = calibrate_eckhardt(Q, recession_segments=[(60, 200)])
    blob = eckhardt_baseflow(Q, bfi_max=bfi_max_cal, a=a_cal)
    assert blob.coefficients["a"] == pytest.approx(a_cal)
    assert blob.coefficients["BFImax"] == pytest.approx(bfi_max_cal)


def test_calibrate_eckhardt_rejects_negative_streamflow():
    Q = np.array([1.0, -0.1, 1.0])
    with pytest.raises(ValueError, match="non-negative"):
        calibrate_eckhardt(Q, recession_segments=[(0, 3)])


def test_calibrate_eckhardt_recovers_constant_a_from_clean_recession():
    """Synthetic clean recession in the middle → calibrated a ≈ true a."""
    n = 300
    a_true = 0.92
    Q = np.full(n, 5.0, dtype=np.float64)
    Q[100:200] = 8.0 * (a_true ** np.arange(100, dtype=np.float64))
    a_cal, _ = calibrate_eckhardt(Q, recession_segments=[(100, 200)])
    assert abs(a_cal - a_true) < 1e-6
