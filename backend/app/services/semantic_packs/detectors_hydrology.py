"""Hydrology semantic-pack detectors (SEG-021).

Each detector matches a shape-primitive segment against a hydrology-specific
domain label.  Detectors share the contract

    detector(X_seg, shape_label, context) -> (matched, confidence)

and *mutate* the ``context`` dict in place to add the metrics that their
matching ``context_predicate`` (defined alongside in ``hydrology.yaml``)
will reference.

The ``baseflow`` detector delegates to the SEG-016 Eckhardt fitter rather
than re-implementing the recursive filter.

References
----------
Eckhardt, K. (2005).  Hydrological Processes 19(2):507–515 — baseflow,
    BFI.
Tallaksen, L. M. (1995).  J. Hydrology 165:349–370 — recession analysis.
Hampel, F. R. (1974).  J. American Statistical Association 69(346):
    383–393 — robust outlier detection.
Wolter, K. & Timlin, M. S. (2011).  Int. J. Climatology 31(7):1074 —
    MEI / ENSO 2–7 yr band.
Mantua, N. & Hare, S. (2002).  J. Oceanography 58:35–44 — PDO 15–30 yr
    band.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

from .core import register_detector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers shared across detectors
# ---------------------------------------------------------------------------


def _series_median(arr: np.ndarray, context: dict[str, Any]) -> float:
    """Resolve ``Q_median``: prefer caller-supplied full-series median over
    the segment-only median (a baseflow segment dragged below 'Q_median'
    against itself would never match)."""
    if "Q_median" in context and context["Q_median"] is not None:
        return float(context["Q_median"])
    if arr.size == 0:
        return 0.0
    return float(np.median(arr))


def _ols_slope(arr: np.ndarray) -> float:
    """OLS slope of ``arr`` against ``np.arange(n)``."""
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


def _dominant_period_samples(arr: np.ndarray) -> float:
    """Dominant period of ``arr`` in samples via FFT power maximum (DC excluded)."""
    n = len(arr)
    if n < 4:
        return 0.0
    centred = arr - float(arr.mean())
    power = np.abs(np.fft.rfft(centred)) ** 2
    if len(power) <= 1:
        return 0.0
    power[0] = 0.0  # discard DC
    if power.max() <= 0.0:
        return 0.0
    k = int(np.argmax(power))
    if k == 0:
        return 0.0
    return float(n) / float(k)


def _hampel_outlier_score(arr: np.ndarray, n_sigma: float = 3.0) -> tuple[bool, float]:
    """Return whether ``arr`` contains a Hampel-style outlier and a confidence
    in ``[0, 1]`` proportional to (peak − median) / (n_sigma · MAD).

    Uses MAD scaled by 1.4826 to approximate σ for Gaussian data
    (Hampel 1974, Eq. 3).
    """
    if arr.size == 0:
        return False, 0.0
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med)))
    if mad <= 0.0:
        # All samples equal: no outlier possible
        return False, 0.0
    sigma = 1.4826 * mad
    peak_dev = float(np.max(np.abs(arr - med)))
    score = peak_dev / max(n_sigma * sigma, 1e-12)
    return score > 1.0, float(min(1.0, max(0.0, (score - 1.0) / 4.0)))


# ---------------------------------------------------------------------------
# baseflow — Eckhardt recursive filter (delegates to SEG-016)
# ---------------------------------------------------------------------------


@register_detector("eckhardt_baseflow")
def detect_baseflow(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Tag a *plateau* segment as ``baseflow`` when the Eckhardt-derived
    baseflow fraction is high and the segment level sits below
    ``BFImax · Q_median`` (caller-supplied full-series median).

    Mutates ``context`` with ``Q_mean``, ``Q_median``, ``BFI``, ``BFImax``.
    The ``context_predicate`` (``Q_mean < BFImax · Q_median``) is evaluated
    by the matcher *after* this detector returns.
    """
    if shape_label != "plateau":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size == 0:
        return False, 0.0

    bfi_max = float(context.get("BFImax", 0.8))
    a = float(context.get("a", 0.98))

    # Delegate the actual recursive filter to SEG-016 so we never duplicate
    # baseflow logic.
    try:
        from app.services.decomposition.fitters.eckhardt import (  # noqa: PLC0415
            fit_eckhardt,
        )
        blob = fit_eckhardt(arr, alpha=a, bfi_max=bfi_max)
        baseflow_arr = blob.components["baseflow"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("eckhardt_baseflow: SEG-016 fitter unavailable (%s)", exc)
        return False, 0.0

    Q_mean = float(np.mean(arr))
    Q_median = _series_median(arr, context)
    bfi = float(np.sum(baseflow_arr) / np.sum(arr)) if float(np.sum(arr)) > 0.0 else 0.0

    context["Q_mean"] = Q_mean
    context["Q_median"] = Q_median
    context["BFI"] = bfi
    context.setdefault("BFImax", bfi_max)

    matched = bfi > 0.5
    return matched, float(bfi)


# ---------------------------------------------------------------------------
# stormflow — peak detection + ascending limb fit
# ---------------------------------------------------------------------------


@register_detector("peak_detection_plus_ascending_limb_fit")
def detect_stormflow(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Tag a *transient* segment as ``stormflow`` when its peak exceeds a
    multiple of the long-term median AND a rising limb is present in the
    first half of the segment.

    Mutates ``context`` with ``peak_Q``, ``Q_median``,
    ``rising_limb_detected``, ``peak_ratio_threshold``.
    """
    if shape_label != "transient":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 3:
        return False, 0.0

    peak_Q = float(np.max(arr))
    Q_median = _series_median(arr, context)
    threshold = float(context.get("peak_ratio_threshold", 3.0))

    half = max(2, len(arr) // 2)
    rising_slope = _ols_slope(arr[:half])
    rising_limb_detected = rising_slope > 0.0

    context["peak_Q"] = peak_Q
    context["Q_median"] = Q_median
    context["rising_limb_detected"] = rising_limb_detected
    context.setdefault("peak_ratio_threshold", threshold)

    matched = rising_limb_detected and peak_Q > threshold * max(Q_median, 1e-12)
    if not matched:
        return False, 0.0
    confidence = min(1.0, max(0.0, peak_Q / (threshold * max(Q_median, 1e-12)) - 1.0))
    return True, float(confidence)


# ---------------------------------------------------------------------------
# peak_flow — Hampel-style outlier on a spike segment
# ---------------------------------------------------------------------------


@register_detector("hampel_peak")
def detect_peak_flow(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Tag a *spike* segment as ``peak_flow`` when a Hampel outlier sits
    above ``5 · Q_median`` and the segment is short enough.

    Mutates ``context`` with ``peak_Q``, ``Q_median``, ``duration_samples``,
    ``dt``.
    """
    if shape_label != "spike":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size == 0:
        return False, 0.0

    has_outlier, outlier_conf = _hampel_outlier_score(arr)
    peak_Q = float(np.max(arr))
    Q_median = _series_median(arr, context)
    dt = float(context.get("dt", 1.0))

    # Spike *width* — the number of samples above 50 % of the peak height,
    # not the total segment length.  A genuine spike is brief: a single
    # outlier surrounded by baseline samples.
    half_height = 0.5 * (peak_Q + Q_median) if peak_Q > Q_median else peak_Q
    duration_samples = int(np.sum(arr >= half_height))

    context["peak_Q"] = peak_Q
    context["Q_median"] = Q_median
    context["duration_samples"] = duration_samples
    context.setdefault("dt", dt)

    matched = has_outlier and peak_Q > 5.0 * max(Q_median, 1e-12)
    if not matched:
        return False, 0.0
    return True, float(outlier_conf)


# ---------------------------------------------------------------------------
# rising_limb / recession_limb — slope-sign + neighbour context
# ---------------------------------------------------------------------------


@register_detector("slope_sign_plus_context")
def detect_slope_sign_plus_context(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Compute slope and pass through neighbour-context flags so that the
    ``rising_limb`` / ``recession_limb`` predicates can decide.

    Mutates ``context`` with ``slope`` and the boolean neighbour flags
    ``preceded_by_baseflow`` / ``follows_peak_flow`` (defaulting to ``False``
    when the caller did not provide them).
    """
    if shape_label != "trend":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 2:
        return False, 0.0

    slope = _ols_slope(arr)

    context["slope"] = slope
    context.setdefault("preceded_by_baseflow", False)
    context.setdefault("follows_peak_flow", False)
    context.setdefault("recession_slope_max", float(context.get("recession_slope_max", 0.1)))

    # The label-specific ``context_predicate`` performs the rising vs
    # recession discrimination; this detector merely confirms a non-zero
    # trend slope.
    matched = abs(slope) > 0.0
    confidence = float(min(1.0, abs(slope) / max(float(np.std(arr)) + 1e-12, 1e-12)))
    return matched, confidence


# ---------------------------------------------------------------------------
# snowmelt_freshet — seasonal + transient
# ---------------------------------------------------------------------------


@register_detector("seasonal_context_plus_transient_fit")
def detect_snowmelt_freshet(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Tag a *transient* segment as ``snowmelt_freshet`` when the calendar
    context flags spring AND the segment shows a sustained multi-week rise.

    Mutates ``context`` with ``is_spring`` (defaulted from caller),
    ``sustained_rise_weeks``, ``slope``.
    """
    if shape_label != "transient":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 7:
        return False, 0.0

    slope = _ols_slope(arr)
    samples_per_week = max(1.0, float(context.get("samples_per_week", 7.0)))
    sustained_rise_weeks = float(arr.size) / samples_per_week if slope > 0.0 else 0.0
    is_spring = bool(context.get("is_spring", False))

    context["slope"] = slope
    context["sustained_rise_weeks"] = sustained_rise_weeks
    context.setdefault("is_spring", is_spring)

    matched = slope > 0.0
    confidence = float(min(1.0, max(0.0, sustained_rise_weeks / 8.0)))  # 8 weeks → full
    return matched, confidence


# ---------------------------------------------------------------------------
# drought — low-flow plateau over a duration threshold
# ---------------------------------------------------------------------------


@register_detector("low_flow_threshold_plus_duration")
def detect_drought(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Tag a *plateau* segment as ``drought`` when the bulk of its samples
    sit below ``0.1 · Q_median`` and the segment lasts > 30 days.

    Mutates ``context`` with ``Q_median``, ``low_flow_fraction``,
    ``duration_days``, ``dt``.
    """
    if shape_label != "plateau":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size == 0:
        return False, 0.0

    Q_median = _series_median(arr, context)
    threshold_q = 0.1 * max(Q_median, 1e-12)
    low_flow_fraction = float(np.mean(arr < threshold_q)) if Q_median > 0.0 else 0.0
    samples_per_day = max(1.0, float(context.get("samples_per_day", 1.0)))
    duration_days = float(arr.size) / samples_per_day

    context["Q_median"] = Q_median
    context["low_flow_fraction"] = low_flow_fraction
    context["duration_days"] = duration_days
    context.setdefault("dt", float(context.get("dt", 1.0)))

    matched = low_flow_fraction > 0.5
    confidence = float(min(1.0, max(0.0, low_flow_fraction)))
    return matched, confidence


# ---------------------------------------------------------------------------
# ENSO_phase — dominant 2–7 yr period (Wolter & Timlin 2011)
# ---------------------------------------------------------------------------


@register_detector("mei_index_plus_period_check")
def detect_enso_phase(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Tag a *cycle* segment as an ``ENSO_phase`` when its dominant period
    sits inside the 2–7 year band (MEI canonical band, Wolter 2011).

    Mutates ``context`` with ``dominant_period_samples`` and
    ``dominant_period_years`` (samples / ``samples_per_year``).
    """
    if shape_label != "cycle":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 8:
        return False, 0.0

    period_samples = _dominant_period_samples(arr)
    samples_per_year = float(context.get("samples_per_year", 12.0))
    period_years = period_samples / samples_per_year if period_samples > 0.0 else 0.0

    context["dominant_period_samples"] = period_samples
    context["dominant_period_years"] = period_years

    matched = period_years > 0.0
    confidence = (
        1.0 if 2.0 <= period_years <= 7.0 else 0.0
    )
    return matched, float(confidence)


# ---------------------------------------------------------------------------
# PDO_phase — dominant 15–30 yr period (Mantua & Hare 2002)
# ---------------------------------------------------------------------------


@register_detector("pdo_index_plus_period_check")
def detect_pdo_phase(
    X_seg: np.ndarray,
    shape_label: str,
    context: dict[str, Any],
) -> tuple[bool, float]:
    """Tag a *cycle* segment as a ``PDO_phase`` when its dominant period
    sits inside the 15–30 year band (Mantua & Hare 2002)."""
    if shape_label != "cycle":
        return False, 0.0
    arr = np.asarray(X_seg, dtype=np.float64).ravel()
    if arr.size < 16:
        return False, 0.0

    period_samples = _dominant_period_samples(arr)
    samples_per_year = float(context.get("samples_per_year", 12.0))
    period_years = period_samples / samples_per_year if period_samples > 0.0 else 0.0

    context["dominant_period_samples"] = period_samples
    context["dominant_period_years"] = period_years

    matched = period_years > 0.0
    confidence = (
        1.0 if 15.0 <= period_years <= 30.0 else 0.0
    )
    return matched, float(confidence)
