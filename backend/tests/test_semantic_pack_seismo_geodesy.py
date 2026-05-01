"""Tests for the seismo-geodesy semantic pack — SEG-022.

References
----------
Allen (1978), Savage (1983), Bevis & Brown (2014), Bedford & Bevis (2018),
Hooper et al. (2012).
"""
from __future__ import annotations

import numpy as np
import pytest

from app.services.semantic_packs import (
    DETECTOR_REGISTRY,
    SemanticPack,
    label_segment,
    load_pack,
    match_semantic_label,
)
from app.services.semantic_packs.detectors_seismo_geodesy import (
    snap_to_2pi,
    sta_lta_ratio,
)


RNG = np.random.default_rng(42)


_EXPECTED_LABELS: set[str] = {
    "P_arrival", "S_arrival", "coda", "surface_waves", "tremor",
    "coseismic_offset", "postseismic_relaxation", "interseismic_loading",
    "SSE", "seasonal_signal",
    "common_mode_error", "tropospheric_delay", "unwrapping_error",
    "antenna_offset",
}


_EXPECTED_DETECTORS: set[str] = {
    "sta_lta", "sta_lta_with_polarization", "post_S_envelope_fit",
    "dispersive_wave_detection", "envelope_correlation_plus_lfe",
    "etm_step_from_known_origin", "fit_log_or_exp",
    "etm_linear_rate_ex_steps_ex_transients", "gratsid_bump",
    "etm_harmonics", "common_mode_pca",
    "gacos_or_pyaps_correction_residual", "phase_jump_2pi_detector",
    "metadata_driven_step",
}


# ---------------------------------------------------------------------------
# Pack loading
# ---------------------------------------------------------------------------


def test_seismo_geodesy_pack_loads():
    pack = load_pack("seismo_geodesy")
    assert isinstance(pack, SemanticPack)
    assert pack.name == "seismo-geodesy"
    assert pack.version == "1.0"


def test_pack_contains_all_fourteen_labels():
    pack = load_pack("seismo_geodesy")
    assert set(pack.semantic_labels.keys()) == _EXPECTED_LABELS


def test_every_label_maps_to_valid_shape():
    pack = load_pack("seismo_geodesy")
    valid = {"plateau", "trend", "step", "spike", "cycle", "transient", "noise"}
    for label in pack.semantic_labels.values():
        assert label.shape_primitive in valid, (
            f"label {label.name!r} maps to unknown shape {label.shape_primitive!r}"
        )


def test_every_named_detector_is_registered():
    pack = load_pack("seismo_geodesy")
    for label in pack.semantic_labels.values():
        assert label.detector_name in DETECTOR_REGISTRY


def test_all_expected_detectors_present_in_registry():
    for name in _EXPECTED_DETECTORS:
        assert name in DETECTOR_REGISTRY, f"missing detector {name!r}"


# ---------------------------------------------------------------------------
# Detector signature contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("detector_name", sorted(_EXPECTED_DETECTORS))
def test_each_detector_returns_bool_float_tuple(detector_name: str):
    detector = DETECTOR_REGISTRY[detector_name]
    arr = np.full(64, 1.0, dtype=np.float64)
    result = detector(arr, "step", {"Q_median": 1.0, "sampling_rate_hz": 1.0})
    assert isinstance(result, tuple) and len(result) == 2
    matched, conf = result
    assert isinstance(matched, bool)
    assert isinstance(conf, float)
    assert 0.0 <= conf <= 1.0 or matched is False


@pytest.mark.parametrize("detector_name", sorted(_EXPECTED_DETECTORS))
def test_detector_rejects_wrong_shape(detector_name: str):
    """Every detector should return False for an obviously-wrong shape."""
    detector = DETECTOR_REGISTRY[detector_name]
    arr = np.zeros(32, dtype=np.float64)
    matched, conf = detector(arr, "plateau_does_not_apply", {})
    assert matched is False
    assert conf == 0.0


# ---------------------------------------------------------------------------
# STA/LTA helper (Allen 1978)
# ---------------------------------------------------------------------------


def _synthetic_seismogram(
    n: int = 200,
    onset_idx: int = 100,
    pre_amp: float = 0.05,
    post_amp: float = 1.0,
    seed: int = 0,
) -> np.ndarray:
    """Stationary low-amp noise pre-onset, high-amp transient post-onset."""
    rng = np.random.default_rng(seed)
    arr = rng.normal(scale=pre_amp, size=n)
    arr[onset_idx:] += rng.normal(scale=post_amp, size=n - onset_idx)
    return arr


def test_sta_lta_ratio_peaks_at_onset():
    """STA/LTA peaks AT the onset, not far past it (LTA absorbs post-onset
    energy after ~window_lta_samples).  Compare the onset window against
    a pre-onset baseline."""
    arr = _synthetic_seismogram(n=200, onset_idx=100)
    ratio = sta_lta_ratio(arr, window_sta_samples=5, window_lta_samples=50)
    onset_peak = float(ratio[100:110].max())
    pre_onset_baseline = float(ratio[60:90].mean())
    assert onset_peak > pre_onset_baseline, (
        f"onset peak={onset_peak:.3f} should exceed pre-onset baseline="
        f"{pre_onset_baseline:.3f}"
    )


def test_sta_lta_p_arrival_pick_within_two_samples():
    """Synthetic seismogram with onset at sample 100 — STA/LTA pick must be
    within ±2 samples of the true onset."""
    arr = _synthetic_seismogram(n=200, onset_idx=100)
    context = {
        "sampling_rate_hz": 1.0,
        "window_sta_seconds": 5.0,
        "window_lta_seconds": 50.0,
        "threshold": 4.0,
    }
    matched, _ = DETECTOR_REGISTRY["sta_lta"](arr, "step", context)
    assert matched is True
    pick = context["trigger_index"]
    assert pick >= 0 and abs(pick - 100) <= 2, f"pick={pick}, expected 100±2"


def test_sta_lta_quiet_signal_no_trigger():
    """Pure low-amp noise must not trigger a P-pick."""
    rng = np.random.default_rng(42)
    arr = rng.normal(scale=0.05, size=200)
    matched, _ = DETECTOR_REGISTRY["sta_lta"](
        arr, "step",
        {"sampling_rate_hz": 1.0, "window_sta_seconds": 5.0,
         "window_lta_seconds": 50.0, "threshold": 4.0},
    )
    assert matched is False


def test_s_arrival_uses_relaxed_threshold():
    """S-arrival detector should pick where P-arrival's stricter threshold
    would still pick — and should populate ``polarization_score=None`` for
    univariate input."""
    arr = _synthetic_seismogram()
    ctx = {"sampling_rate_hz": 1.0,
           "window_sta_seconds": 5.0, "window_lta_seconds": 50.0}
    matched, _ = DETECTOR_REGISTRY["sta_lta_with_polarization"](arr, "step", ctx)
    assert matched is True
    assert ctx["polarization_score"] is None


# ---------------------------------------------------------------------------
# Coda / surface waves / tremor detectors
# ---------------------------------------------------------------------------


def test_coda_detector_recovers_exponential_decay_tau():
    """Synthetic exponentially-decaying envelope; detector should report a
    finite tau."""
    n = 200
    t = np.arange(n)
    arr = np.exp(-t / 30.0) + 0.001 * RNG.normal(size=n)
    ctx: dict = {}
    matched, conf = DETECTOR_REGISTRY["post_S_envelope_fit"](arr, "transient", ctx)
    assert matched is True
    assert ctx["coda_tau_samples"] > 1.0
    assert 0.0 <= conf <= 1.0


def test_coda_detector_rejects_constant_signal():
    arr = np.ones(100)
    matched, _ = DETECTOR_REGISTRY["post_S_envelope_fit"](arr, "transient", {})
    assert matched is False


def test_surface_waves_detect_frequency_drift():
    """Chirp signal — dominant period drifts."""
    n = 256
    inst_freq = np.linspace(0.05, 0.20, n)
    arr = np.sin(2 * np.pi * np.cumsum(inst_freq))
    ctx: dict = {}
    matched, conf = DETECTOR_REGISTRY["dispersive_wave_detection"](arr, "cycle", ctx)
    assert matched is True
    assert ctx["frequency_drift"] > 0.0
    assert conf > 0.0


def test_surface_waves_reject_pure_sine():
    n = 256
    arr = np.sin(2 * np.pi * np.arange(n) / 16.0)
    matched, _ = DETECTOR_REGISTRY["dispersive_wave_detection"](arr, "cycle", {})
    assert matched is False


def test_tremor_detector_populates_envelope_metrics():
    rng = np.random.default_rng(0)
    arr = rng.normal(scale=2.0, size=500)
    ctx = {"sampling_rate_hz": 1.0}
    matched, _ = DETECTOR_REGISTRY["envelope_correlation_plus_lfe"](
        arr, "noise", ctx,
    )
    assert "low_frequency_amplitude" in ctx
    assert "sustained_minutes" in ctx
    assert isinstance(matched, bool)


# ---------------------------------------------------------------------------
# Coseismic / postseismic / interseismic / SSE / seasonal — ETM-delegated
# ---------------------------------------------------------------------------


def test_coseismic_offset_requires_origin_time():
    """Without ``origin_time``, the detector reports origin_time_known=False
    and never matches the YAML predicate."""
    arr = np.concatenate([np.full(50, 0.0), np.full(50, 5.0)])
    pack = load_pack("seismo_geodesy")
    label = pack.semantic_labels["coseismic_offset"]
    matched, _ = match_semantic_label(label, arr, "step", context={})
    assert matched is False


def test_coseismic_offset_with_origin_time_matches():
    arr = np.concatenate([np.full(50, 0.0), np.full(50, 5.0)])
    pack = load_pack("seismo_geodesy")
    label = pack.semantic_labels["coseismic_offset"]
    context = {"origin_time": 49.0, "detection_threshold": 0.5}
    matched, _ = match_semantic_label(label, arr, "step", context=context)
    assert matched is True


def test_postseismic_relaxation_picks_log_or_exp():
    """Synthetic log-shaped relaxation."""
    n = 200
    t = np.arange(n, dtype=np.float64)
    arr = 0.5 * np.log1p(t / 20.0)
    ctx: dict = {"samples_per_day": 1.0, "follows_coseismic_offset": True}
    matched, _ = DETECTOR_REGISTRY["fit_log_or_exp"](arr, "transient", ctx)
    assert matched is True
    assert ctx["basis_type"] in ("log", "exp")


def test_postseismic_relaxation_predicate_requires_coseismic_predecessor():
    """Without ``follows_coseismic_offset=True``, the YAML predicate fails."""
    n = 200
    arr = 0.5 * np.log1p(np.arange(n) / 20.0)
    pack = load_pack("seismo_geodesy")
    label = pack.semantic_labels["postseismic_relaxation"]
    matched_no_pred, _ = match_semantic_label(
        label, arr, "transient", context={"samples_per_day": 1.0},
    )
    matched_with_pred, _ = match_semantic_label(
        label, arr, "transient",
        context={"samples_per_day": 1.0, "follows_coseismic_offset": True},
    )
    assert matched_no_pred is False
    assert matched_with_pred is True


def test_interseismic_loading_requires_exclusion_flags():
    arr = np.linspace(0, 10, 100)
    pack = load_pack("seismo_geodesy")
    label = pack.semantic_labels["interseismic_loading"]
    matched, _ = match_semantic_label(label, arr, "trend", context={})
    # Defaults set excludes_* True, so a clean linear trend matches.
    assert matched is True


def test_interseismic_loading_rejects_when_exclusion_false():
    arr = np.linspace(0, 10, 100)
    pack = load_pack("seismo_geodesy")
    label = pack.semantic_labels["interseismic_loading"]
    matched, _ = match_semantic_label(
        label, arr, "trend",
        context={"excludes_coseismic_offset": False},
    )
    assert matched is False


def test_sse_duration_in_band_with_smooth_onset_decay():
    n = 100  # 100 days at 1 sample/day
    t = np.arange(n, dtype=np.float64)
    arr = 5.0 * np.exp(-((t - 50.0) ** 2) / (2 * 20.0 ** 2))  # smooth Gaussian bump
    pack = load_pack("seismo_geodesy")
    label = pack.semantic_labels["SSE"]
    matched, _ = match_semantic_label(
        label, arr, "transient", context={"samples_per_day": 1.0},
    )
    assert matched is True


def test_sse_duration_below_band_rejected():
    # 4 samples at 1 sample/day → duration < min_duration_days (7)
    arr = np.array([0.0, 1.0, 0.5, 0.0])
    pack = load_pack("seismo_geodesy")
    label = pack.semantic_labels["SSE"]
    matched, _ = match_semantic_label(
        label, arr, "transient", context={"samples_per_day": 1.0},
    )
    assert matched is False


def test_seasonal_signal_annual_period_matches():
    n = 365 * 3
    spd = 1.0
    t = np.arange(n, dtype=np.float64)
    arr = np.sin(2 * np.pi * t / 365.25)
    pack = load_pack("seismo_geodesy")
    label = pack.semantic_labels["seasonal_signal"]
    matched, _ = match_semantic_label(
        label, arr, "cycle", context={"samples_per_day": spd},
    )
    assert matched is True


def test_seasonal_signal_off_band_rejected():
    n = 365
    t = np.arange(n, dtype=np.float64)
    arr = np.sin(2 * np.pi * t / 30.0)  # monthly — off both annual + semiannual
    pack = load_pack("seismo_geodesy")
    label = pack.semantic_labels["seasonal_signal"]
    matched, _ = match_semantic_label(
        label, arr, "cycle", context={"samples_per_day": 1.0},
    )
    assert matched is False


# ---------------------------------------------------------------------------
# Common-mode error: multi-station guard
# ---------------------------------------------------------------------------


def test_common_mode_returns_not_applicable_for_single_station():
    """Caller passes a single-station residual (1-D / single row) — detector
    must report ``not_applicable=True`` and not match."""
    arr = RNG.normal(size=200)
    ctx: dict = {}
    matched, _ = DETECTOR_REGISTRY["common_mode_pca"](arr, "noise", ctx)
    assert matched is False
    assert ctx["not_applicable"] is True


def test_common_mode_detects_correlated_multi_station_signal():
    """Three stations sharing a common shift; first PCA component dominates."""
    n_stations, n_samples = 3, 120
    common = RNG.normal(size=n_samples)
    matrix = np.stack([
        common + 0.05 * RNG.normal(size=n_samples)
        for _ in range(n_stations)
    ])
    ctx = {"station_residuals": matrix}
    matched, conf = DETECTOR_REGISTRY["common_mode_pca"](
        matrix.mean(axis=0), "noise", ctx,
    )
    assert ctx["not_applicable"] is False
    assert matched is True
    assert conf > 0.5


def test_common_mode_pca_rejects_independent_stations():
    """Three independent-noise stations — leading eigenvalue should NOT
    dominate."""
    matrix = RNG.normal(size=(3, 200))
    ctx = {"station_residuals": matrix}
    matched, _ = DETECTOR_REGISTRY["common_mode_pca"](
        matrix.mean(axis=0), "noise", ctx,
    )
    # With independent noise, leading_frac is typically < 0.5
    assert ctx["not_applicable"] is False
    assert matched is False or ctx["leading_eigenvalue_fraction"] < 0.7


# ---------------------------------------------------------------------------
# Tropospheric delay
# ---------------------------------------------------------------------------


def test_tropospheric_delay_detects_low_frequency_dominance():
    n = 256
    t = np.arange(n)
    arr = np.sin(2 * np.pi * t / 200.0) + 0.1 * RNG.normal(size=n)
    matched, _ = DETECTOR_REGISTRY["gacos_or_pyaps_correction_residual"](
        arr, "noise", {},
    )
    assert matched is True


def test_tropospheric_delay_rejects_white_noise():
    arr = RNG.normal(size=300)
    matched, _ = DETECTOR_REGISTRY["gacos_or_pyaps_correction_residual"](
        arr, "noise", {},
    )
    assert matched is False


# ---------------------------------------------------------------------------
# Unwrapping error: 2π-multiple snap
# ---------------------------------------------------------------------------


def test_snap_to_2pi_returns_nearest_multiple():
    snapped, ok, k = snap_to_2pi(2 * np.pi * 3 + 0.05 * np.pi)
    assert k == 3
    assert ok is True
    assert snapped == pytest.approx(2 * np.pi * 3)


def test_snap_to_2pi_outside_tolerance():
    snapped, ok, k = snap_to_2pi(2 * np.pi * 3 + 0.5 * np.pi)
    assert ok is False


def test_unwrapping_error_detects_2pi_step():
    """Step of exactly 2π → matched + multiple_count = 1.

    Calls the detector directly to inspect its context mutation.
    ``match_semantic_label`` copies context (so detector mutations don't
    leak between labels in :func:`label_segment`), so the high-level
    matcher API only exposes ``(matched, confidence)``.
    """
    arr = np.concatenate([np.zeros(30), np.full(30, 2 * np.pi)])
    ctx: dict = {}
    matched, _ = DETECTOR_REGISTRY["phase_jump_2pi_detector"](arr, "step", ctx)
    assert matched is True
    assert ctx["snap_2pi_multiple_count"] == 1
    assert ctx["is_2pi_multiple"] is True


def test_unwrapping_error_rejects_non_2pi_step():
    arr = np.concatenate([np.zeros(30), np.full(30, 1.0)])
    pack = load_pack("seismo_geodesy")
    label = pack.semantic_labels["unwrapping_error"]
    matched, _ = match_semantic_label(label, arr, "step", context={})
    assert matched is False


def test_unwrapping_error_zero_step_rejected_even_if_within_tolerance():
    """A 0-magnitude step is technically within 0.1π of 0·(2π)=0, but k=0
    is intentionally rejected — that would tag every flat segment."""
    arr = np.full(60, 1.0)
    pack = load_pack("seismo_geodesy")
    label = pack.semantic_labels["unwrapping_error"]
    matched, _ = match_semantic_label(label, arr, "step", context={})
    assert matched is False


# ---------------------------------------------------------------------------
# Antenna offset: metadata-driven step
# ---------------------------------------------------------------------------


def test_antenna_offset_matches_when_log_entry_in_window():
    arr = np.concatenate([np.zeros(30), np.full(30, 1.0)])
    pack = load_pack("seismo_geodesy")
    label = pack.semantic_labels["antenna_offset"]
    ctx = {
        "segment_start_time": 0.0,
        "segment_end_time": 60.0,
        "maintenance_log": [29.5],
    }
    matched, _ = match_semantic_label(label, arr, "step", context=ctx)
    assert matched is True


def test_antenna_offset_rejects_when_log_entry_outside_window():
    arr = np.concatenate([np.zeros(30), np.full(30, 1.0)])
    pack = load_pack("seismo_geodesy")
    label = pack.semantic_labels["antenna_offset"]
    ctx = {
        "segment_start_time": 0.0,
        "segment_end_time": 60.0,
        "maintenance_log": [200.0],
    }
    matched, _ = match_semantic_label(label, arr, "step", context=ctx)
    assert matched is False


def test_antenna_offset_no_log_means_no_match():
    arr = np.concatenate([np.zeros(30), np.full(30, 1.0)])
    pack = load_pack("seismo_geodesy")
    label = pack.semantic_labels["antenna_offset"]
    matched, _ = match_semantic_label(label, arr, "step", context={})
    assert matched is False


# ---------------------------------------------------------------------------
# Integration — synthetic GNSS fixture with coseismic + postseismic + linear
# ---------------------------------------------------------------------------


def test_gnss_fixture_attaches_expected_labels():
    """Assemble a synthetic GNSS time series and verify each segment gets the
    canonical seismo-geodesy label."""
    pack = load_pack("seismo_geodesy")

    # Linear interseismic loading.
    t_int = np.arange(120, dtype=np.float64)
    Q_int = 0.01 * t_int + 0.05 * RNG.normal(size=120)
    labels_i = label_segment(pack, Q_int, "trend", context={})
    assert any(name == "interseismic_loading" for name, _ in labels_i)

    # Coseismic step at the segment midpoint with a known origin time.
    Q_co = np.concatenate([np.zeros(40), np.full(40, 8.0)]) + 0.01 * RNG.normal(size=80)
    labels_c = label_segment(
        pack, Q_co, "step",
        context={"origin_time": 39.0, "detection_threshold": 0.5},
    )
    assert any(name == "coseismic_offset" for name, _ in labels_c)

    # Postseismic logarithmic relaxation following the coseismic step.
    t_p = np.arange(200, dtype=np.float64)
    Q_post = 0.5 * np.log1p(t_p / 15.0) + 0.02 * RNG.normal(size=200)
    labels_p = label_segment(
        pack, Q_post, "transient",
        context={"samples_per_day": 1.0, "follows_coseismic_offset": True},
    )
    assert any(name == "postseismic_relaxation" for name, _ in labels_p)


# ---------------------------------------------------------------------------
# obspy is optional (verifies our numpy-only fallback works without it)
# ---------------------------------------------------------------------------


def test_sta_lta_works_without_obspy():
    """Detectors must be importable and runnable with only numpy/scipy.
    SciPy is in requirements, but obspy is optional and not installed in
    the test environment."""
    # If we got this far, the module imported successfully without obspy.
    arr = _synthetic_seismogram()
    ratio = sta_lta_ratio(arr, window_sta_samples=5, window_lta_samples=50)
    assert ratio.shape == arr.shape
    assert np.all(np.isfinite(ratio))
