"""Tier-2 trend ops: flatten, reverse_direction, change_slope, linearise,
extrapolate, add_acceleration (OP-021).

Dispatches by blob.method:
  'ETM'        — edits coefficients['linear_rate'] and components['linear_rate'].
  'LandTrendr' — edits coefficients['slope_1'/'slope_2'] and recomputes
                 components['trend'] from updated piecewise coefficients.

All mutating ops deepcopy the blob internally; the caller's blob is unchanged.

Relabeling:
  flatten                    → DETERMINISTIC('plateau')
  change_slope(alpha=0)      → DETERMINISTIC('plateau')
  change_slope(alpha≠0)      → PRESERVED('trend')
  reverse_direction          → PRESERVED('trend')
  linearise                  → PRESERVED('trend')
  extrapolate                → PRESERVED('trend')
  add_acceleration           → PRESERVED('trend')

References
----------
Sen, P. K. (1968). Estimates of the regression coefficient based on
    Kendall's tau. J. Am. Stat. Assoc. 63(324):1379-1389.
    → linearise Theil-Sen robust slope.

Bevis, M. & Brown, S. (2014). Trajectory models and reference frames for
    crustal motion geodesy. J. Geodesy 88:283-311. DOI 10.1007/s00190-013-0685-5.
    → ETM linear-rate coefficient (x0 + linear_rate * t).

Kennedy, R. E., Yang, Z., & Cohen, W. B. (2010). Detecting trends in forest
    disturbance and recovery using yearly Landsat time series. Remote Sensing
    of Environment 114(12):2897-2910.
    → LandTrendr per-segment slope editing.
"""

from __future__ import annotations

import copy
import logging

import numpy as np
from scipy.stats import theilslopes

from app.models.decomposition import DecompositionBlob
from app.services.operations.tier2.plateau import Tier2OpResult
from app.services.operations.relabeler.relabeler import RelabelResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inline relabeler helpers
# ---------------------------------------------------------------------------


def _preserved(pre_shape: str) -> RelabelResult:
    return RelabelResult(
        new_shape=pre_shape,
        confidence=1.0,
        needs_resegment=False,
        rule_class="PRESERVED",
    )


def _deterministic(target_shape: str) -> RelabelResult:
    return RelabelResult(
        new_shape=target_shape,
        confidence=1.0,
        needs_resegment=False,
        rule_class="DETERMINISTIC",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _recompute_lt_trend(blob: DecompositionBlob, t: np.ndarray) -> np.ndarray:
    """Rebuild the LandTrendr trend array from updated slope/intercept coefficients."""
    brk = int(blob.coefficients.get("breakpoint", len(t) // 2))
    brk = max(0, min(brk, len(t)))
    s1 = float(blob.coefficients.get("slope_1", 0.0))
    i1 = float(blob.coefficients.get("intercept_1", 0.0))
    s2 = float(blob.coefficients.get("slope_2", 0.0))
    i2 = float(blob.coefficients.get("intercept_2", 0.0))
    trend = np.empty(len(t), dtype=np.float64)
    trend[:brk] = i1 + s1 * t[:brk]
    trend[brk:] = i2 + s2 * t[brk:]
    return trend


def _zero_etm_linear_rate(blob: DecompositionBlob, n: int) -> None:
    """Set ETM linear_rate coefficient and component to zero."""
    blob.coefficients["linear_rate"] = 0.0
    blob.components["linear_rate"] = np.zeros(n, dtype=np.float64)


def _scale_etm_linear_rate(blob: DecompositionBlob, alpha: float) -> None:
    """Scale ETM linear_rate coefficient and component by alpha."""
    blob.coefficients["linear_rate"] = float(blob.coefficients.get("linear_rate", 0.0)) * alpha
    if "linear_rate" in blob.components:
        blob.components["linear_rate"] = blob.components["linear_rate"] * alpha
    else:
        logger.warning(
            "trend._scale_etm_linear_rate: 'linear_rate' missing from components; "
            "skipping component update."
        )


def _collapse_lt_to_constant(blob: DecompositionBlob, t: np.ndarray) -> None:
    """Collapse a LandTrendr blob to Constant method at the trend mean level.

    Called when slope is zeroed on a LandTrendr blob to avoid the
    intercept_1 ≠ intercept_2 step artefact that would remain if only the
    slopes were zeroed.
    """
    n = len(t)
    level = float(np.mean(blob.components.get("trend", np.zeros(n))))
    blob.method = "Constant"
    blob.coefficients = {"level": level}
    blob.components = {
        "trend": np.full(n, level, dtype=np.float64),
        "residual": np.zeros(n, dtype=np.float64),
    }
    blob.residual = np.zeros(n, dtype=np.float64)


# ---------------------------------------------------------------------------
# flatten
# ---------------------------------------------------------------------------


def flatten(
    blob: DecompositionBlob,
    t: np.ndarray,
    pre_shape: str = "trend",
) -> Tier2OpResult:
    """Flatten the trend to a constant plateau by zeroing the linear rate.

    Equivalent to change_slope(alpha=0): both produce an identical reassembled
    series.  The level is preserved from the non-linear components (x0 for ETM,
    mean trend for LandTrendr).

    Relabeling: DETERMINISTIC('plateau').

    Reference: Bevis & Brown (2014) — ETM linear-rate component set to 0.

    Args:
        blob:      ETM or LandTrendr DecompositionBlob.
        t:         Time axis for the segment, shape (n,).
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with flattened values and DETERMINISTIC('plateau').
    """
    return change_slope(blob, alpha=0.0, t=t, pre_shape=pre_shape)


# ---------------------------------------------------------------------------
# change_slope
# ---------------------------------------------------------------------------


def change_slope(
    blob: DecompositionBlob,
    alpha: float,
    t: np.ndarray,
    pre_shape: str = "trend",
) -> Tier2OpResult:
    """Scale the linear rate by alpha.

    alpha=1.0 → identity; alpha=-1.0 → reverse direction; alpha=0.0 → flatten.

    For ETM: multiplies coefficients['linear_rate'] and the corresponding
    component array by alpha.
    For LandTrendr: multiplies slope_1 and slope_2 by alpha.  When alpha=0,
    collapses to a Constant blob at the trend mean (avoids step artefact at
    the breakpoint when intercepts differ).

    Relabeling: DETERMINISTIC('plateau') if alpha==0, else PRESERVED('trend').

    References: Bevis & Brown (2014) Eq. 1; Kennedy et al. (2010).

    Args:
        blob:      ETM or LandTrendr DecompositionBlob.
        alpha:     Scale factor for the linear rate.
        t:         Time axis for the segment, shape (n,).
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with scaled-slope values and appropriate relabeling.
    """
    blob = copy.deepcopy(blob)
    t_arr = np.asarray(t, dtype=np.float64)
    n = len(t_arr)

    if blob.method == "ETM":
        if float(alpha) == 0.0:
            _zero_etm_linear_rate(blob, n)
        else:
            _scale_etm_linear_rate(blob, float(alpha))
    elif blob.method == "LandTrendr":
        if float(alpha) == 0.0:
            _collapse_lt_to_constant(blob, t_arr)
        else:
            blob.coefficients["slope_1"] = float(blob.coefficients.get("slope_1", 0.0)) * alpha
            blob.coefficients["slope_2"] = float(blob.coefficients.get("slope_2", 0.0)) * alpha
            blob.components["trend"] = _recompute_lt_trend(blob, t_arr)
    else:
        logger.warning(
            "trend.change_slope: unsupported blob method '%s'; applying raw value scaling.",
            blob.method,
        )
        if float(alpha) == 0.0:
            for key in blob.components:
                blob.components[key] = np.zeros_like(blob.components[key])
        else:
            for key in blob.components:
                if key != "residual":
                    blob.components[key] = blob.components[key] * float(alpha)

    relabel = _deterministic("plateau") if float(alpha) == 0.0 else _preserved(pre_shape)
    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=relabel,
        op_name="change_slope",
    )


# ---------------------------------------------------------------------------
# reverse_direction
# ---------------------------------------------------------------------------


def reverse_direction(
    blob: DecompositionBlob,
    t: np.ndarray,
    pre_shape: str = "trend",
) -> Tier2OpResult:
    """Reverse the sign of the linear rate (negate the slope).

    Equivalent to change_slope(alpha=-1).

    Relabeling: PRESERVED('trend') — a negated slope is still a trend.

    References: Bevis & Brown (2014); Kennedy et al. (2010).

    Args:
        blob:      ETM or LandTrendr DecompositionBlob.
        t:         Time axis for the segment, shape (n,).
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with negated-slope values and PRESERVED('trend').
    """
    result = change_slope(blob, alpha=-1.0, t=t, pre_shape=pre_shape)
    return Tier2OpResult(
        values=result.values,
        relabel=_preserved(pre_shape),
        op_name="reverse_direction",
    )


# ---------------------------------------------------------------------------
# linearise
# ---------------------------------------------------------------------------


def linearise(
    blob: DecompositionBlob,
    X_orig: np.ndarray,
    t: np.ndarray,
    pre_shape: str = "trend",
) -> Tier2OpResult:
    """Refit the trend as a single robust linear model (Theil-Sen).

    Replaces the current decomposition (ETM, LandTrendr, or any method) with
    an ETM blob whose linear_rate is the Theil-Sen median slope of X_orig.
    The x0 intercept is the corresponding Theil-Sen intercept.

    For LandTrendr blobs this 'collapses vertices to 2 endpoints' — the
    piecewise structure is replaced by a single linear fit.

    Relabeling: PRESERVED('trend').

    Reference: Sen (1968) §3 — Theil-Sen estimator via scipy.stats.theilslopes.

    Args:
        blob:      Any DecompositionBlob for the segment.
        X_orig:    Original (or current edited) signal values, shape (n,).
        t:         Time axis for the segment, shape (n,).
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with Theil-Sen fitted values and PRESERVED('trend').
    """
    blob = copy.deepcopy(blob)
    X_arr = np.asarray(X_orig, dtype=np.float64)
    t_arr = np.asarray(t, dtype=np.float64)
    n = len(t_arr)

    result = theilslopes(X_arr, t_arr)
    slope = float(result.slope)
    intercept = float(result.intercept)

    # x0 is anchored at t[0] so the fitted line passes through (t[0], x0_at_t0).
    # Residual is stored in blob.residual only — not in components — so that
    # reassemble() returns the clean fitted line, not the original signal.
    x0_at_t0 = float(intercept + slope * t_arr[0])
    residual = X_arr - (intercept + slope * t_arr)

    blob.method = "ETM"
    blob.coefficients = {"x0": x0_at_t0, "linear_rate": slope}
    blob.components = {
        "x0": np.full(n, x0_at_t0, dtype=np.float64),
        "linear_rate": slope * (t_arr - t_arr[0]),
    }
    blob.residual = residual

    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="linearise",
    )


# ---------------------------------------------------------------------------
# extrapolate
# ---------------------------------------------------------------------------


def extrapolate(
    blob: DecompositionBlob,
    t_extended: np.ndarray,
    pre_shape: str = "trend",
) -> Tier2OpResult:
    """Evaluate the trend model at an (optionally extended) time axis.

    For ETM: x(t) = x0 + linear_rate * t_extended  (absolute t, matching the
        ETM fitter convention: intercept x0 corresponds to t=0, not t=t_ext[0]).
    For LandTrendr: x(t) = intercept_2 + slope_2 * t_extended  (absolute t,
        matching the LandTrendr fitter convention used in _recompute_lt_trend).

    t_extended may exceed the bounds of the original segment.  The blob is
    not mutated.

    Relabeling: PRESERVED('trend').

    References: Bevis & Brown (2014); Kennedy et al. (2010).

    Args:
        blob:       ETM or LandTrendr DecompositionBlob.
        t_extended: Time axis at which to evaluate, shape (m,).
        pre_shape:  Shape label before the edit.

    Returns:
        Tier2OpResult with extrapolated values of length m and PRESERVED('trend').
    """
    t_ext = np.asarray(t_extended, dtype=np.float64)

    if blob.method == "ETM":
        x0 = float(blob.coefficients.get("x0", 0.0))
        beta = float(blob.coefficients.get("linear_rate", 0.0))
        values = x0 + beta * t_ext
    elif blob.method == "LandTrendr":
        s2 = float(blob.coefficients.get("slope_2", 0.0))
        i2 = float(blob.coefficients.get("intercept_2", 0.0))
        values = i2 + s2 * t_ext
    else:
        logger.warning(
            "trend.extrapolate: unsupported blob method '%s'; using mean trend + zero slope.",
            blob.method,
        )
        component_vals = list(blob.components.values())
        mean_val = float(np.mean(component_vals[0])) if component_vals else 0.0
        values = np.full(len(t_ext), mean_val, dtype=np.float64)

    return Tier2OpResult(
        values=values,
        relabel=_preserved(pre_shape),
        op_name="extrapolate",
    )


# ---------------------------------------------------------------------------
# add_acceleration
# ---------------------------------------------------------------------------


def add_acceleration(
    blob: DecompositionBlob,
    c: float,
    t: np.ndarray,
    pre_shape: str = "trend",
) -> Tier2OpResult:
    """Add a quadratic acceleration term: accel(t) = c * (t - t[0])².

    Works with both ETM and LandTrendr blobs by appending an 'acceleration'
    component and coefficient.  Any prior 'acceleration' component is replaced.

    Relabeling: PRESERVED('trend') — the signal remains trend-shaped; the
    relabeler is not re-invoked (OP-040 rule table designates 'trend' as the
    PRESERVED default for add_acceleration).

    Reference: Bevis & Brown (2014) Eq. 1 — acceleration extends the linear
    model by adding a quadratic term.

    Args:
        blob:      ETM or LandTrendr DecompositionBlob.
        c:         Quadratic coefficient (value units per time² units).
        t:         Time axis for the segment, shape (n,).
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with acceleration-augmented values and PRESERVED('trend').
    """
    blob = copy.deepcopy(blob)
    t_arr = np.asarray(t, dtype=np.float64)
    accel = float(c) * (t_arr - t_arr[0]) ** 2
    blob.coefficients["acceleration"] = float(c)
    blob.components["acceleration"] = accel

    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="add_acceleration",
    )
