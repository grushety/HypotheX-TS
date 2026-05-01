"""Tests for the remote-sensing semantic pack — SEG-023.

References
----------
Jönsson & Eklundh (2002, 2004), Verbesselt et al. (2010),
Kennedy et al. (2010), Yunjun et al. (2019).
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


RNG = np.random.default_rng(42)


_EXPECTED_LABELS: set[str] = {
    "greenup", "senescence", "peak_of_season", "dormancy",
    "disturbance", "recovery",
    "wet_up", "dry_down",
    "heatwave", "coldwave",
    "cloud_gap", "APS",
    "seasonal_deformation", "linear_deformation",
}


_EXPECTED_DETECTORS: set[str] = {
    "timesat_threshold", "mstl_peak_window", "low_amplitude_plus_duration",
    "bfast_breakpoint", "landtrendr_positive_slope_post_disturbance",
    "slope_plus_context", "percentile_threshold_plus_duration",
    "missingness_mask", "gacos_correction_residual",
    "mstl_annual_component", "etm_linear_rate",
}


# ---------------------------------------------------------------------------
# Pack loading
# ---------------------------------------------------------------------------


def test_remote_sensing_pack_loads():
    pack = load_pack("remote_sensing")
    assert isinstance(pack, SemanticPack)
    assert pack.name == "remote-sensing"
    assert pack.version == "1.0"


def test_pack_contains_all_fourteen_labels():
    pack = load_pack("remote_sensing")
    assert set(pack.semantic_labels.keys()) == _EXPECTED_LABELS


def test_every_label_maps_to_valid_shape():
    pack = load_pack("remote_sensing")
    valid = {"plateau", "trend", "step", "spike", "cycle", "transient", "noise"}
    for label in pack.semantic_labels.values():
        assert label.shape_primitive in valid


def test_every_named_detector_is_registered():
    pack = load_pack("remote_sensing")
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
    result = detector(arr, "trend", {})
    assert isinstance(result, tuple) and len(result) == 2
    matched, conf = result
    assert isinstance(matched, bool)
    assert isinstance(conf, float)
    assert 0.0 <= conf <= 1.0 or matched is False


@pytest.mark.parametrize("detector_name", sorted(_EXPECTED_DETECTORS))
def test_detector_rejects_wrong_shape(detector_name: str):
    detector = DETECTOR_REGISTRY[detector_name]
    arr = np.zeros(32, dtype=np.float64)
    matched, conf = detector(arr, "_definitely_wrong_shape_", {})
    assert matched is False
    assert conf == 0.0


# ---------------------------------------------------------------------------
# Phenology — TIMESAT-style SOS / EOS / peak / dormancy
# ---------------------------------------------------------------------------


def test_greenup_fires_on_rising_segment_crossing_20_percent():
    """NDVI rising from 0.1 → 0.6 across a spring window crosses the 20 %
    threshold (annual_min=0.1, annual_max=0.6 → threshold = 0.1 + 0.2*0.5 = 0.2)."""
    arr = np.linspace(0.1, 0.6, 30)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["greenup"]
    ctx = {
        "annual_min": 0.1,
        "annual_max": 0.6,
        "is_in_window": True,
    }
    matched, _ = match_semantic_label(label, arr, "trend", context=ctx)
    assert matched is True


def test_greenup_rejected_outside_spring_window():
    arr = np.linspace(0.1, 0.6, 30)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["greenup"]
    ctx = {"annual_min": 0.1, "annual_max": 0.6, "is_in_window": False}
    matched, _ = match_semantic_label(label, arr, "trend", context=ctx)
    assert matched is False


def test_senescence_fires_on_falling_segment_crossing_80_percent():
    """NDVI falling from 0.6 → 0.1 crosses the 80 % threshold (= 0.5)."""
    arr = np.linspace(0.6, 0.1, 30)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["senescence"]
    ctx = {"annual_min": 0.1, "annual_max": 0.6, "is_in_window": True}
    matched, _ = match_semantic_label(label, arr, "trend", context=ctx)
    assert matched is True


def test_timesat_threshold_records_threshold_value():
    arr = np.linspace(0.1, 0.6, 30)
    ctx = {"annual_min": 0.1, "annual_max": 0.6, "threshold_percent": 20.0}
    DETECTOR_REGISTRY["timesat_threshold"](arr, "trend", ctx)
    assert ctx["threshold_value"] == pytest.approx(0.1 + 0.2 * 0.5)


def test_peak_of_season_fires_on_short_high_plateau():
    """A 14-day plateau at 90 % of annual max is a peak."""
    arr = np.full(14, 0.55)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["peak_of_season"]
    ctx = {"annual_max": 0.60, "samples_per_day": 1.0}
    matched, _ = match_semantic_label(label, arr, "plateau", context=ctx)
    assert matched is True


def test_peak_of_season_rejects_long_high_plateau():
    """A 90-day high plateau is more like an extended growing season."""
    arr = np.full(90, 0.55)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["peak_of_season"]
    ctx = {"annual_max": 0.60, "samples_per_day": 1.0}
    matched, _ = match_semantic_label(label, arr, "plateau", context=ctx)
    assert matched is False


def test_dormancy_fires_on_long_low_plateau():
    arr = np.full(120, 0.05)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["dormancy"]
    ctx = {"annual_max": 0.60, "samples_per_day": 1.0}
    matched, _ = match_semantic_label(label, arr, "plateau", context=ctx)
    assert matched is True


def test_dormancy_rejects_short_low_plateau():
    arr = np.full(20, 0.05)  # only 20 days
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["dormancy"]
    ctx = {"annual_max": 0.60, "samples_per_day": 1.0}
    matched, _ = match_semantic_label(label, arr, "plateau", context=ctx)
    assert matched is False


# ---------------------------------------------------------------------------
# Disturbance — BFAST-delegated breakpoint
# ---------------------------------------------------------------------------


def test_disturbance_fires_on_negative_step():
    """NDVI drop from 0.6 → 0.2 = magnitude −0.4 < threshold −0.2."""
    arr = np.concatenate([np.full(30, 0.6), np.full(30, 0.2)])
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["disturbance"]
    matched, _ = match_semantic_label(label, arr, "step", context={})
    assert matched is True


def test_disturbance_rejects_positive_step():
    arr = np.concatenate([np.full(30, 0.2), np.full(30, 0.6)])
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["disturbance"]
    matched, _ = match_semantic_label(label, arr, "step", context={})
    assert matched is False


def test_disturbance_rejects_small_negative_step_below_threshold():
    """Drop of −0.05 does NOT exceed the default magnitude_threshold of −0.2."""
    arr = np.concatenate([np.full(30, 0.55), np.full(30, 0.50)])
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["disturbance"]
    matched, _ = match_semantic_label(label, arr, "step", context={})
    assert matched is False


def test_disturbance_detector_populates_breakpoint_index():
    arr = np.concatenate([np.full(30, 0.6), np.full(30, 0.2)])
    ctx: dict = {}
    DETECTOR_REGISTRY["bfast_breakpoint"](arr, "step", ctx)
    assert "bfast_breakpoint_index" in ctx
    assert "negative_step_magnitude" in ctx


# ---------------------------------------------------------------------------
# Recovery — LandTrendr-delegated post-disturbance positive slope
# ---------------------------------------------------------------------------


def test_recovery_fires_on_positive_slope_following_disturbance():
    """Steep recovery: slope ≈ 0.1/sample > min_recovery_slope of 0.05."""
    arr = np.linspace(0.2, 1.2, 10)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["recovery"]
    matched, _ = match_semantic_label(
        label, arr, "trend", context={"follows_disturbance": True},
    )
    assert matched is True


def test_recovery_rejects_when_follows_disturbance_false():
    arr = np.linspace(0.2, 1.2, 10)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["recovery"]
    matched, _ = match_semantic_label(label, arr, "trend", context={})
    assert matched is False


def test_recovery_rejects_when_slope_below_min():
    """Slope of 0.001 is below default min_recovery_slope of 0.05."""
    arr = np.linspace(0.2, 0.25, 50)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["recovery"]
    matched, _ = match_semantic_label(
        label, arr, "trend", context={"follows_disturbance": True},
    )
    assert matched is False


# ---------------------------------------------------------------------------
# wet_up / dry_down — slope sign + neighbour context
# ---------------------------------------------------------------------------


def test_wet_up_requires_positive_slope_and_follows_dry_down():
    arr = np.linspace(0.1, 0.5, 30)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["wet_up"]
    no_neighbour, _ = match_semantic_label(label, arr, "trend", context={})
    with_neighbour, _ = match_semantic_label(
        label, arr, "trend", context={"follows_dry_down": True},
    )
    assert no_neighbour is False
    assert with_neighbour is True


def test_dry_down_requires_negative_slope_and_follows_wet_up():
    arr = np.linspace(0.5, 0.1, 30)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["dry_down"]
    matched, _ = match_semantic_label(
        label, arr, "trend", context={"follows_wet_up": True},
    )
    assert matched is True


# ---------------------------------------------------------------------------
# Heatwave / coldwave — percentile threshold + duration
# ---------------------------------------------------------------------------


def test_heatwave_fires_on_4_day_segment_above_p95():
    arr = np.full(4, 35.0)  # high LST
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["heatwave"]
    ctx = {"series_p95": 32.0, "series_p5": 5.0, "samples_per_day": 1.0}
    matched, _ = match_semantic_label(label, arr, "transient", context=ctx)
    assert matched is True


def test_heatwave_rejects_2_day_segment_below_duration_threshold():
    arr = np.full(2, 35.0)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["heatwave"]
    ctx = {"series_p95": 32.0, "series_p5": 5.0, "samples_per_day": 1.0}
    matched, _ = match_semantic_label(label, arr, "transient", context=ctx)
    assert matched is False


def test_coldwave_fires_on_segment_below_p5():
    arr = np.full(4, -5.0)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["coldwave"]
    ctx = {"series_p95": 32.0, "series_p5": 0.0, "samples_per_day": 1.0}
    matched, _ = match_semantic_label(label, arr, "transient", context=ctx)
    assert matched is True


def test_heatwave_does_not_match_coldwave_segment():
    """A cold segment must NOT trigger the heatwave label."""
    arr = np.full(4, -5.0)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["heatwave"]
    ctx = {"series_p95": 32.0, "series_p5": 0.0, "samples_per_day": 1.0}
    matched, _ = match_semantic_label(label, arr, "transient", context=ctx)
    assert matched is False


# ---------------------------------------------------------------------------
# Cloud gap — metadata-driven, no NaN interpolation
# ---------------------------------------------------------------------------


def test_cloud_gap_fires_when_mask_present():
    arr = np.zeros(20)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["cloud_gap"]
    matched, _ = match_semantic_label(
        label, arr, "noise", context={"is_cloud_gap": True, "cloud_fraction": 0.95},
    )
    assert matched is True


def test_cloud_gap_rejects_when_mask_false():
    arr = np.zeros(20)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["cloud_gap"]
    matched, _ = match_semantic_label(label, arr, "noise", context={})
    assert matched is False


def test_cloud_gap_does_not_call_interpolation():
    """Per AC: cloud_gap detector reads missingness mask, NEVER interpolates
    NaNs.  Verify that even with NaN-filled X_seg, the detector simply
    consults the mask and returns."""
    arr = np.full(20, np.nan)
    ctx = {"is_cloud_gap": True}
    # Should not raise on NaN input (the detector ignores X_seg values).
    matched, conf = DETECTOR_REGISTRY["missingness_mask"](arr, "noise", ctx)
    assert matched is True


# ---------------------------------------------------------------------------
# APS — atmospheric phase screen (low-frequency dominance)
# ---------------------------------------------------------------------------


def test_aps_detects_low_frequency_dominance():
    n = 256
    t = np.arange(n)
    arr = np.sin(2 * np.pi * t / 200.0) + 0.1 * RNG.normal(size=n)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["APS"]
    matched, _ = match_semantic_label(label, arr, "noise", context={})
    assert matched is True


def test_aps_rejects_white_noise():
    arr = RNG.normal(size=300)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["APS"]
    matched, _ = match_semantic_label(label, arr, "noise", context={})
    assert matched is False


# ---------------------------------------------------------------------------
# Seasonal deformation — annual ± 30 days
# ---------------------------------------------------------------------------


def test_seasonal_deformation_fires_for_annual_period():
    n = 365 * 3
    t = np.arange(n, dtype=np.float64)
    arr = np.sin(2 * np.pi * t / 365.0)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["seasonal_deformation"]
    matched, _ = match_semantic_label(
        label, arr, "cycle", context={"samples_per_day": 1.0},
    )
    assert matched is True


def test_seasonal_deformation_rejects_monthly_period():
    n = 365
    t = np.arange(n, dtype=np.float64)
    arr = np.sin(2 * np.pi * t / 30.0)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["seasonal_deformation"]
    matched, _ = match_semantic_label(
        label, arr, "cycle", context={"samples_per_day": 1.0},
    )
    assert matched is False


def test_seasonal_deformation_records_period_days():
    n = 365 * 3
    arr = np.sin(2 * np.pi * np.arange(n) / 365.0)
    ctx = {"samples_per_day": 1.0}
    DETECTOR_REGISTRY["mstl_annual_component"](arr, "cycle", ctx)
    assert abs(ctx["dominant_period_days"] - 365.0) <= 30.0


# ---------------------------------------------------------------------------
# Linear deformation — ETM-delegated linear rate
# ---------------------------------------------------------------------------


def test_linear_deformation_fires_on_non_zero_slope():
    arr = np.linspace(0.0, 5.0, 50)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["linear_deformation"]
    matched, _ = match_semantic_label(label, arr, "trend", context={})
    assert matched is True


def test_linear_deformation_rejects_below_velocity_threshold():
    """Slope is small; predicate threshold is high."""
    arr = np.linspace(0.0, 0.001, 50)
    pack = load_pack("remote_sensing")
    label = pack.semantic_labels["linear_deformation"]
    matched, _ = match_semantic_label(
        label, arr, "trend", context={"velocity_threshold": 1.0},
    )
    assert matched is False


# ---------------------------------------------------------------------------
# Integration — synthetic NDVI fixture with greenup → peak → senescence → dormancy
# ---------------------------------------------------------------------------


def _ndvi_phenology_segments() -> dict[str, np.ndarray]:
    """Four canonical phenology segments at sample/day cadence."""
    annual_min, annual_max = 0.1, 0.6
    return {
        "greenup":     np.linspace(annual_min, annual_max, 60),
        "peak":        np.full(20, annual_max),
        "senescence":  np.linspace(annual_max, annual_min, 60),
        "dormancy":    np.full(150, annual_min),
    }


def test_phenology_segments_match_expected_labels():
    pack = load_pack("remote_sensing")
    segments = _ndvi_phenology_segments()
    annual_ctx = {
        "annual_min": 0.1,
        "annual_max": 0.6,
        "samples_per_day": 1.0,
        "is_in_window": True,
    }

    labels_g = label_segment(
        pack, segments["greenup"], "trend", context=annual_ctx,
    )
    assert any(name == "greenup" for name, _ in labels_g)

    labels_p = label_segment(
        pack, segments["peak"], "plateau", context=annual_ctx,
    )
    assert any(name == "peak_of_season" for name, _ in labels_p)

    labels_s = label_segment(
        pack, segments["senescence"], "trend", context=annual_ctx,
    )
    assert any(name == "senescence" for name, _ in labels_s)

    labels_d = label_segment(
        pack, segments["dormancy"], "plateau", context=annual_ctx,
    )
    assert any(name == "dormancy" for name, _ in labels_d)


def test_bfast_disturbance_fixture_attaches_label():
    """Synthetic NDVI step from 0.65 → 0.30 (forest fire signature)."""
    arr = np.concatenate([
        np.full(40, 0.65) + 0.01 * RNG.normal(size=40),
        np.full(40, 0.30) + 0.01 * RNG.normal(size=40),
    ])
    pack = load_pack("remote_sensing")
    labels = label_segment(pack, arr, "step", context={})
    assert any(name == "disturbance" for name, _ in labels), (
        f"expected 'disturbance' label, got {labels}"
    )


def test_insar_annual_period_attaches_seasonal_deformation_label():
    n = 365 * 3
    t = np.arange(n, dtype=np.float64)
    arr = 0.005 * np.sin(2 * np.pi * t / 365.0) + 0.0005 * RNG.normal(size=n)
    pack = load_pack("remote_sensing")
    labels = label_segment(
        pack, arr, "cycle", context={"samples_per_day": 1.0},
    )
    assert any(name == "seasonal_deformation" for name, _ in labels)


# ---------------------------------------------------------------------------
# Cross-pack registry — confirm SEG-021 / SEG-022 detectors not clobbered
# ---------------------------------------------------------------------------


def test_seg021_and_seg022_detectors_still_present_after_seg023_load():
    for name in ("eckhardt_baseflow", "sta_lta", "common_mode_pca"):
        assert name in DETECTOR_REGISTRY
