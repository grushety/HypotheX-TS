"""Remote-sensing semantic-pack detectors (SEG-023).

Each detector matches a shape-primitive segment against a remote-sensing
phenology / disturbance / InSAR domain label.  Detectors share the
contract

    detector(X_seg, shape_label, context) -> (matched, confidence)

and *mutate* the ``context`` dict in place to add the metrics that the
matching ``context_predicate`` in ``remote_sensing.yaml`` references.

Three of the detectors delegate to existing fitters so that no
parametric fitting logic is duplicated:

* ``bfast_breakpoint`` → SEG-015 ``fit_bfast`` (disturbance step)
* ``landtrendr_positive_slope_post_disturbance`` → SEG-017
  ``fit_landtrendr`` (post-disturbance recovery slope)
* ``etm_linear_rate`` → SEG-013 ``fit_etm`` (InSAR linear velocity)

References
----------
Jönsson, P. & Eklundh, L. (2002, 2004).  TIMESAT — a program for
    analyzing time-series of satellite sensor data.  *Computers &
    Geosciences* 30:833–845.
    → SOS / EOS amplitude-threshold definitions; Table 1 default
    20 % / 80 % thresholds.
Verbesselt, J., Hyndman, R., Newnham, G., & Culvenor, D. (2010).  RSE
    114(1):106–115.  → BFAST disturbance breakpoint.
Kennedy, R., Yang, Z., & Cohen, W. (2010).  RSE 114(12):2897–2910.
    → LandTrendr trajectory segmentation; recovery is a positive-slope
    segment following a negative-slope disturbance.
Yunjun, Z., Fattahi, H., & Amelung, F. (2019).  Computers &
    Geosciences 133:104331.  → APS / atmospheric phase screen residual
    after GACOS correction.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

from .core import register_detector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ols_slope(arr: np.ndarray) -> float:
    n = len(arr)
    if n < 2:
        return 0.0
    t = np.arange(n, dtype=np.float64)
    t_mean = t.mean()
    a_mean = float(arr.mean())
    denom = float(((t - t_mean) ** 2).sum())
    if denom <= 0.0:
        return 0.0
    return float(((t - t_mean) * (arr - a_mean)).sum()) / denom


def _samples_per_day(context: dict[str, Any]) -> float:
    return float(context.get("samples_per_day", 1.0))


def _dominant_period_samples(arr: np.ndarray) -> float:
    n = len(arr)
    if n < 4:
        return 0.0
    centred = arr - float(arr.mean())
    power = np.abs(np.fft.rfft(centred)) ** 2
    if len(power) <= 1:
        return 0.0
    power[0] = 0.0
    if power.max() <= 0.0:
        return 0.0
    k = int(np.argmax(power))
    if k == 0:
        return 0.0
    return float(n) / float(k)


def _annual_amplitude(arr: np.ndarray, context: dict[str, Any]) -> float:
    """Resolve the annual amplitude — prefer caller-supplied value over the
    segment's local range, since SOS/EOS thresholds are defined relative to
    the *full season's* min-to-max range (Jönsson 2004 §2)."""
    if "annual_amplitude" in context:
        return float(context["annual_amplitude"])
    if "annual_min" in context and "annual_max" in context:
        return float(context["annual_max"]) - float(context["annual_min"])
    if arr.size == 0:
        return 0.0
    return float(np.max(arr) - np.min(arr))


def _annual_min(arr: np.ndarray, context: dict[str, Any]) -> float:
    if "annual_min" in context:
        return float(context["annual_min"])
    if arr.size == 0:
        return 0.0
    return float(np.min(arr))


def _annual_max(arr: np.ndarray, context: dict[str, Any]) -> float:
    if "annual_max" in context:
        return float(context["annual_max"])
    if arr.size == 0:
        return 0.0
    return float(np.max(arr))


# ---------------------------------------------------------------------------
# Phenology — SOS / EOS / peak / dormancy
# ---------------------------------------------------------------------------


@register_detector("timesat_threshold")
def detect_timesat_threshold(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """SOS / EOS detector per Jönsson & Eklundh (2004) Table 1 — fires when
    the segment crosses ``threshold_percent`` of the annual amplitude
    relative to the annual minimum.

    Same callable serves ``greenup`` (positive slope, spring window,
    20 %) and ``senescence`` (negative slope, autumn window, 80 %); the
    YAML predicate distinguishes by sign-of-slope and the caller-supplied
    ``is_in_window`` flag.

    Mutates ``context`` with ``slope``, ``crosses_threshold``,
    ``threshold_value``, ``threshold_percent``, ``is_in_window``,
    ``annual_min``, ``annual_max``, ``annual_amplitude``.
    """
    if shape_label != "trend":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 2:
        return False, 0.0

    threshold_percent = float(context.get("threshold_percent", 20.0))
    annual_min = _annual_min(arr, context)
    annual_max = _annual_max(arr, context)
    amplitude = max(annual_max - annual_min, 0.0)
    threshold_value = annual_min + (threshold_percent / 100.0) * amplitude

    slope = _ols_slope(arr)
    crosses = bool(arr.min() <= threshold_value <= arr.max())

    context["slope"] = slope
    context["threshold_value"] = float(threshold_value)
    context["threshold_percent"] = threshold_percent
    context["crosses_threshold"] = crosses
    context["annual_min"] = annual_min
    context["annual_max"] = annual_max
    context["annual_amplitude"] = amplitude
    context.setdefault("is_in_window", True)

    matched = crosses and abs(slope) > 0.0
    confidence = float(min(1.0, abs(slope) / max(amplitude / max(arr.size, 1) + 1e-12, 1e-12)))
    return matched, confidence


@register_detector("mstl_peak_window")
def detect_peak_of_season(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Peak-of-season detector — a *plateau* near the annual maximum that
    lasts only briefly (Jönsson 2004).

    Mutates ``context`` with ``amplitude_above_max_ratio``,
    ``duration_short``, ``annual_max``, ``samples_per_day``,
    ``duration_days``.
    """
    if shape_label != "plateau":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size == 0:
        return False, 0.0

    annual_max = _annual_max(arr, context)
    seg_mean = float(np.mean(arr))
    ratio = seg_mean / max(annual_max, 1e-12) if annual_max > 0.0 else 0.0
    spd = _samples_per_day(context)
    duration_days = float(arr.size) / spd
    short = duration_days < 60.0  # peak windows are weeks, not seasons

    context["amplitude_above_max_ratio"] = float(ratio)
    context["annual_max"] = annual_max
    context["samples_per_day"] = spd
    context["duration_days"] = duration_days
    context["duration_short"] = bool(short)

    matched = ratio > 0.9 and short
    confidence = float(min(1.0, max(0.0, ratio)))
    return matched, confidence


@register_detector("low_amplitude_plus_duration")
def detect_dormancy(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Dormancy detector — a *plateau* whose level sits well below the
    annual maximum for an extended period.

    Mutates ``context`` with ``amplitude_below_max_ratio``,
    ``duration_long``, ``annual_max``, ``duration_days``.
    """
    if shape_label != "plateau":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size == 0:
        return False, 0.0

    annual_max = _annual_max(arr, context)
    seg_mean = float(np.mean(arr))
    ratio_below = 1.0 - seg_mean / max(annual_max, 1e-12) if annual_max > 0.0 else 0.0
    spd = _samples_per_day(context)
    duration_days = float(arr.size) / spd
    long_enough = duration_days >= 60.0  # dormancy lasts months

    context["amplitude_below_max_ratio"] = float(ratio_below)
    context["annual_max"] = annual_max
    context["samples_per_day"] = spd
    context["duration_days"] = duration_days
    context["duration_long"] = bool(long_enough)

    matched = ratio_below > 0.8 and long_enough
    confidence = float(min(1.0, max(0.0, ratio_below)))
    return matched, confidence


# ---------------------------------------------------------------------------
# Disturbance — delegate to BFAST (SEG-015)
# ---------------------------------------------------------------------------


@register_detector("bfast_breakpoint")
def detect_disturbance(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Disturbance detector — a *step* segment whose BFAST-derived level
    drop exceeds ``magnitude_threshold`` (negative number; default
    ``-0.2`` for NDVI-style indices).

    Delegates to SEG-015 ``fit_bfast`` so we never re-implement BFAST
    breakpoint logic.

    Mutates ``context`` with ``negative_step_magnitude``,
    ``magnitude_threshold``, ``bfast_breakpoint_index``.
    """
    if shape_label != "step":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 4:
        return False, 0.0

    magnitude_threshold = float(context.get("magnitude_threshold", -0.2))

    # Default magnitude: pre/post-mid mean difference (works without BFAST).
    mid = arr.size // 2
    pre_mean = float(np.mean(arr[:mid])) if mid > 0 else float(arr[0])
    post_mean = float(np.mean(arr[mid:])) if mid < arr.size else float(arr[-1])
    fallback_magnitude = post_mean - pre_mean
    bp_index = mid

    try:
        from app.services.decomposition.fitters.bfast import (  # noqa: PLC0415
            fit_bfast,
        )
        period = int(context.get("period", 12))
        blob = fit_bfast(arr, period=period)
        if "breakpoint" in blob.coefficients:
            bp_index = int(blob.coefficients["breakpoint"])
        if "level_left" in blob.coefficients and "level_right" in blob.coefficients:
            level_l = float(blob.coefficients["level_left"])
            level_r = float(blob.coefficients["level_right"])
            magnitude = level_r - level_l
        else:
            magnitude = fallback_magnitude
    except Exception as exc:  # noqa: BLE001
        logger.warning("bfast_breakpoint: SEG-015 fitter unavailable (%s)", exc)
        magnitude = fallback_magnitude

    context["negative_step_magnitude"] = float(magnitude)
    context["magnitude_threshold"] = magnitude_threshold
    context["bfast_breakpoint_index"] = int(bp_index)

    matched = magnitude < magnitude_threshold
    confidence = float(min(1.0, max(0.0, abs(magnitude) / max(abs(magnitude_threshold), 1e-12) - 1.0)))
    return matched, confidence


# ---------------------------------------------------------------------------
# Recovery — delegate to LandTrendr (SEG-017)
# ---------------------------------------------------------------------------


@register_detector("landtrendr_positive_slope_post_disturbance")
def detect_recovery(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Recovery detector — a *trend* segment with positive slope that
    follows a disturbance event (Kennedy 2010).

    Delegates to SEG-017 ``fit_landtrendr`` for the post-segment slope
    (``slope_2`` in the legacy LandTrendr coefficient schema).  Falls
    back to OLS when the LandTrendr fitter is unavailable.

    Mutates ``context`` with ``slope``, ``min_recovery_slope``,
    ``follows_disturbance``.
    """
    if shape_label != "trend":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 2:
        return False, 0.0

    min_slope = float(context.get("min_recovery_slope", 0.05))
    slope = _ols_slope(arr)

    try:
        from app.services.decomposition.fitters.landtrendr import (  # noqa: PLC0415
            fit_landtrendr,
        )
        blob = fit_landtrendr(arr)
        if "slope_2" in blob.coefficients:
            slope = float(blob.coefficients["slope_2"])
        elif "slopes" in blob.coefficients and blob.coefficients["slopes"]:
            slope = float(blob.coefficients["slopes"][-1])
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "landtrendr_positive_slope_post_disturbance: SEG-017 fitter "
            "unavailable (%s)", exc,
        )

    context["slope"] = float(slope)
    context["min_recovery_slope"] = min_slope
    context.setdefault("follows_disturbance", False)

    matched = slope > min_slope
    confidence = float(min(1.0, max(0.0, slope / max(min_slope, 1e-12) - 1.0)))
    return matched, confidence


# ---------------------------------------------------------------------------
# wet_up / dry_down — same callable, predicate disambiguates
# ---------------------------------------------------------------------------


@register_detector("slope_plus_context")
def detect_wet_dry_trend(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Soil-moisture wet_up / dry_down detector — populates the slope and
    the caller-supplied neighbour flags ``follows_dry_down`` /
    ``follows_wet_up`` so the YAML predicate can disambiguate by sign.

    Mutates ``context`` with ``slope``, ``follows_dry_down``,
    ``follows_wet_up``.
    """
    if shape_label != "trend":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 2:
        return False, 0.0

    slope = _ols_slope(arr)
    context["slope"] = slope
    context.setdefault("follows_dry_down", False)
    context.setdefault("follows_wet_up", False)

    matched = abs(slope) > 0.0
    std = float(np.std(arr))
    confidence = float(min(1.0, abs(slope) / max(std + 1e-12, 1e-12)))
    return matched, confidence


# ---------------------------------------------------------------------------
# heatwave / coldwave — percentile threshold + duration
# ---------------------------------------------------------------------------


@register_detector("percentile_threshold_plus_duration")
def detect_temperature_extreme(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Heatwave / coldwave detector — caller supplies series-wide ``p95``
    and ``p5`` percentiles; segment fires when its mean is above / below
    the corresponding tail and lasts ≥ 3 days.

    Same callable serves both labels (predicates disambiguate by checking
    ``mean_above_p95`` vs ``mean_below_p5``).

    Mutates ``context`` with ``mean_value``, ``mean_above_p95``,
    ``mean_below_p5``, ``duration_days``, ``samples_per_day``,
    ``series_p95``, ``series_p5``.
    """
    if shape_label != "transient":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size == 0:
        return False, 0.0

    spd = _samples_per_day(context)
    duration_days = float(arr.size) / spd
    seg_mean = float(np.mean(arr))

    p95 = context.get("series_p95")
    p5 = context.get("series_p5")
    if p95 is None:
        p95 = float(np.quantile(arr, 0.95))
    if p5 is None:
        p5 = float(np.quantile(arr, 0.05))
    p95 = float(p95)
    p5 = float(p5)

    above_p95 = seg_mean >= p95
    below_p5 = seg_mean <= p5

    context["mean_value"] = seg_mean
    context["mean_above_p95"] = bool(above_p95)
    context["mean_below_p5"] = bool(below_p5)
    context["duration_days"] = duration_days
    context["samples_per_day"] = spd
    context["series_p95"] = p95
    context["series_p5"] = p5

    matched = (above_p95 or below_p5) and duration_days >= 3.0
    confidence = 1.0 if matched else 0.0
    return matched, float(confidence)


# ---------------------------------------------------------------------------
# Cloud gap — driven by data-loader missingness mask
# ---------------------------------------------------------------------------


@register_detector("missingness_mask")
def detect_cloud_gap(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Cloud-gap detector — purely metadata-driven.  Reads
    ``context['is_cloud_gap']`` (set by the data loader before the
    classifier runs); does NOT do any NaN interpolation per the AC.

    Mutates ``context`` with ``missingness_mask_value``,
    ``cloud_fraction``.
    """
    if shape_label != "noise":
        return False, 0.0
    is_gap = bool(context.get("is_cloud_gap", False))
    cloud_fraction = float(context.get("cloud_fraction", 1.0 if is_gap else 0.0))

    context["missingness_mask_value"] = is_gap
    context["cloud_fraction"] = cloud_fraction

    matched = is_gap
    confidence = cloud_fraction if is_gap else 0.0
    return matched, float(confidence)


# ---------------------------------------------------------------------------
# APS — atmospheric phase screen
# ---------------------------------------------------------------------------


@register_detector("gacos_correction_residual")
def detect_aps(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Atmospheric Phase Screen (APS) detector — a *noise* segment whose
    spectrum is dominated by low-frequency content, the GACOS / pyAPS
    correction-residual signature (Yunjun et al. 2019).

    Mutates ``context`` with ``low_frequency_power_fraction``,
    ``is_atmospheric_pattern``.
    """
    if shape_label != "noise":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 8:
        return False, 0.0

    centred = arr - float(arr.mean())
    power = np.abs(np.fft.rfft(centred)) ** 2
    if power.size <= 1:
        return False, 0.0
    power[0] = 0.0
    total = float(power.sum())
    if total <= 0.0:
        return False, 0.0
    cutoff = max(1, power.size // 8)
    lf_frac = float(power[: cutoff + 1].sum() / total)

    context["low_frequency_power_fraction"] = lf_frac
    context["is_atmospheric_pattern"] = lf_frac > 0.6

    matched = lf_frac > 0.6
    return matched, lf_frac


# ---------------------------------------------------------------------------
# Seasonal deformation — MSTL annual component (period ≈ 365 ± 30 days)
# ---------------------------------------------------------------------------


@register_detector("mstl_annual_component")
def detect_seasonal_deformation(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Seasonal-deformation detector — a *cycle* segment whose dominant
    period sits within ``annual ± tolerance_days`` (per AC: 365 ± 30 d).

    Computes the dominant period directly via FFT for cheap-path
    efficiency; the YAML predicate gate ensures only annual-period cycles
    are accepted.  Mutates ``context`` with ``dominant_period_days``,
    ``is_annual_period``, ``annual_tolerance_days``.
    """
    if shape_label != "cycle":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 8:
        return False, 0.0

    spd = _samples_per_day(context)
    period_samples = _dominant_period_samples(arr)
    period_days = period_samples / spd if period_samples > 0.0 else 0.0
    tolerance = float(context.get("annual_tolerance_days", 30.0))
    is_annual = abs(period_days - 365.0) <= tolerance

    context["dominant_period_days"] = float(period_days)
    context["is_annual_period"] = bool(is_annual)
    context["annual_tolerance_days"] = tolerance

    matched = is_annual
    confidence = 1.0 if is_annual else 0.0
    return matched, float(confidence)


# ---------------------------------------------------------------------------
# Linear deformation — delegate to ETM (SEG-013)
# ---------------------------------------------------------------------------


@register_detector("etm_linear_rate")
def detect_linear_deformation(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """InSAR linear-deformation detector — a *trend* segment whose ETM
    linear-rate magnitude exceeds ``velocity_threshold``.

    Delegates to SEG-013 ``fit_etm`` to extract the ``linear_rate``
    coefficient.

    Mutates ``context`` with ``linear_rate``, ``velocity_threshold``.
    """
    if shape_label != "trend":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 4:
        return False, 0.0

    velocity_threshold = float(context.get("velocity_threshold", 0.0))
    rate = _ols_slope(arr)

    try:
        from app.services.decomposition.fitters.etm import fit_etm  # noqa: PLC0415
        blob = fit_etm(arr)
        if "linear_rate" in blob.coefficients:
            rate = float(blob.coefficients["linear_rate"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("etm_linear_rate: SEG-013 fitter unavailable (%s)", exc)

    context["linear_rate"] = float(rate)
    context["velocity_threshold"] = velocity_threshold

    matched = abs(rate) > velocity_threshold
    confidence = float(min(1.0, max(0.0, abs(rate) / max(velocity_threshold + 1e-9, 1e-9) - 1.0)))
    return matched, confidence
