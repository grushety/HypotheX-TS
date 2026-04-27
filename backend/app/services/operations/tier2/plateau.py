"""Tier-2 plateau ops: raise_lower, invert, replace_with_trend, replace_with_cycle,
tilt_detrend (OP-020).

All five operations take a Constant-method DecompositionBlob and return a
Tier2OpResult.  Ops that replace the shape type (replace_with_trend,
replace_with_cycle) mutate blob.method and blob.components in place; the
others either mutate only the level coefficient (raise_lower) or do not
mutate the blob at all (invert, tilt_detrend).  Callers should deepcopy the
blob before passing it when they need to preserve the original.

Relabeling (inline OP-040 rule-table subset for plateau):
  raise_lower       → PRESERVED('plateau')
  invert            → PRESERVED('plateau')
  replace_with_trend → DETERMINISTIC('trend')
  replace_with_cycle → DETERMINISTIC('cycle')
  tilt_detrend      → PRESERVED('plateau')

References
----------
Cleveland, R. B., Cleveland, W. S., McRae, J. E., & Terpenning, I. (1990).
    STL: A Seasonal-Trend Decomposition Procedure Based on Loess.
    Journal of Official Statistics 6(1):3-73.
    → replace_with_cycle STL component layout.

Bevis, M. & Brown, S. (2014). Trajectory models and reference frames for
    crustal motion geodesy. J. Geodesy 88:283-311. DOI 10.1007/s00190-013-0685-5.
    → replace_with_trend ETM intercept + linear-rate components.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass

import numpy as np

from app.models.decomposition import DecompositionBlob
from app.services.operations.relabeler.relabeler import RelabelResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True, eq=False)
class Tier2OpResult:
    """Result of a Tier-2 per-shape operation.

    Attributes:
        values:   Reassembled edited segment values (numpy array).
        relabel:  Relabeling decision.
        op_name:  Operation name for audit emission.
        tier:     Always 2.
    """

    values: np.ndarray
    relabel: RelabelResult
    op_name: str
    tier: int = 2


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


def _level(blob: DecompositionBlob) -> float:
    """Extract the plateau level from a Constant blob."""
    if "level" in blob.coefficients:
        return float(blob.coefficients["level"])
    trend = blob.components.get("trend")
    if trend is not None:
        return float(np.mean(trend))
    components = list(blob.components.values())
    if not components:
        raise ValueError(
            "_level: DecompositionBlob has no 'level' coefficient and no components — "
            "cannot determine plateau level."
        )
    return float(np.mean(components[0]))


# ---------------------------------------------------------------------------
# raise_lower
# ---------------------------------------------------------------------------


def raise_lower(
    blob: DecompositionBlob,
    *,
    delta: float | None = None,
    alpha: float | None = None,
    pivot_mean: float | None = None,
    pre_shape: str = "plateau",
) -> Tier2OpResult:
    """Raise or lower the plateau level additively (delta) or multiplicatively (alpha).

    Exactly one of `delta` or `alpha` must be supplied.

    delta  — additive offset:   new_level = old_level + delta
    alpha  — fractional scale:  new_level = pivot + (1+alpha) * (old_level - pivot)
             where pivot = pivot_mean if given, else 0.0.
             Examples: alpha=0.1 with pivot=0 → 10 % increase.

    Relabeling: PRESERVED('plateau').  Elementary arithmetic; no external paper
    required (additive/multiplicative shift of a scalar level).

    The blob is mutated on an internal copy; the caller's blob is unchanged.

    Args:
        blob:       Constant-method DecompositionBlob.
        delta:      Absolute additive change to the level.
        alpha:      Fractional scale factor relative to pivot.
        pivot_mean: Pivot for alpha-mode scaling; defaults to 0.0.
        pre_shape:  Shape label before the edit.

    Returns:
        Tier2OpResult with reassembled values and PRESERVED relabeling.

    Raises:
        ValueError: If neither or both of delta/alpha are provided.
    """
    if (delta is None) == (alpha is None):
        raise ValueError(
            "raise_lower: exactly one of 'delta' or 'alpha' must be provided "
            f"(got delta={delta!r}, alpha={alpha!r})."
        )

    blob = copy.deepcopy(blob)
    old_level = _level(blob)

    if delta is not None:
        new_level = old_level + float(delta)
    else:
        pivot = float(pivot_mean) if pivot_mean is not None else 0.0
        new_level = pivot + (1.0 + float(alpha)) * (old_level - pivot)  # type: ignore[arg-type]

    blob.coefficients["level"] = new_level
    blob.components["trend"] = np.full_like(blob.components["trend"], new_level)

    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_preserved(pre_shape),
        op_name="raise_lower",
    )


# ---------------------------------------------------------------------------
# invert
# ---------------------------------------------------------------------------


def invert(
    blob: DecompositionBlob,
    mu_global: float,
    pre_shape: str = "plateau",
) -> Tier2OpResult:
    """Reflect the plateau through a global mean: new_value = 2*mu_global - value.

    The blob is not mutated.

    Relabeling: PRESERVED('plateau') — reflection preserves plateau shape.
    Elementary arithmetic (signal reflection); no external paper required.

    Args:
        blob:       Constant-method DecompositionBlob.
        mu_global:  Global mean of the reference baseline (reflection axis).
        pre_shape:  Shape label before the edit.

    Returns:
        Tier2OpResult with inverted values and PRESERVED relabeling.
    """
    signal = blob.reassemble()
    inverted = 2.0 * float(mu_global) - signal
    return Tier2OpResult(
        values=inverted,
        relabel=_preserved(pre_shape),
        op_name="invert",
    )


# ---------------------------------------------------------------------------
# replace_with_trend
# ---------------------------------------------------------------------------


def replace_with_trend(
    blob: DecompositionBlob,
    beta: float,
    t: np.ndarray,
    pre_shape: str = "plateau",
) -> Tier2OpResult:
    """Replace the plateau with a linear ETM trend centred on the plateau level.

    The plateau level becomes the ETM intercept x0.  The reconstructed signal:
        x(t) = x0 + beta * (t - t[0])

    The blob is mutated on an internal copy; the caller's blob is unchanged.

    Relabeling: DETERMINISTIC('trend').

    Reference: Bevis & Brown (2014) Eq. 1 — intercept x0 + linear rate.

    Args:
        blob:      Constant-method DecompositionBlob.
        beta:      Linear drift rate (value units per time-step unit).
        t:         Time axis for the segment, shape (n,).
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with ETM-reconstructed values and DETERMINISTIC('trend').
    """
    blob = copy.deepcopy(blob)
    t_arr = np.asarray(t, dtype=np.float64)
    n = len(t_arr)
    x0 = _level(blob)
    t_centered = t_arr - t_arr[0]

    blob.method = "ETM"
    blob.coefficients = {"x0": x0, "linear_rate": float(beta)}
    blob.components = {
        "x0": np.full(n, x0, dtype=np.float64),
        "linear_rate": float(beta) * t_centered,
        "residual": np.zeros(n, dtype=np.float64),
    }
    blob.residual = np.zeros(n, dtype=np.float64)

    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_deterministic("trend"),
        op_name="replace_with_trend",
    )


# ---------------------------------------------------------------------------
# replace_with_cycle
# ---------------------------------------------------------------------------


def replace_with_cycle(
    blob: DecompositionBlob,
    amplitude: float,
    period: float,
    phase: float,
    t: np.ndarray,
    pre_shape: str = "plateau",
) -> Tier2OpResult:
    """Replace the plateau with a sinusoidal STL cycle.

    The plateau level becomes the STL trend baseline.  The seasonal component:
        S(t) = amplitude * sin(2π*(t - t[0]) / period + phase)

    The blob is mutated on an internal copy; the caller's blob is unchanged.

    Relabeling: DETERMINISTIC('cycle').

    Reference: Cleveland et al. (1990) §1 — STL trend + seasonal layout.

    Args:
        blob:      Constant-method DecompositionBlob.
        amplitude: Half-amplitude of the sinusoidal component.
        period:    Cycle period in time-axis units (must be > 0).
        phase:     Phase offset in radians.
        t:         Time axis for the segment, shape (n,).
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with STL-reconstructed values and DETERMINISTIC('cycle').

    Raises:
        ValueError: If period <= 0.
    """
    if float(period) <= 0.0:
        raise ValueError(f"replace_with_cycle: period must be > 0, got {period!r}.")
    blob = copy.deepcopy(blob)
    t_arr = np.asarray(t, dtype=np.float64)
    n = len(t_arr)
    level = _level(blob)
    t_centered = t_arr - t_arr[0]
    seasonal = float(amplitude) * np.sin(
        2.0 * np.pi * t_centered / float(period) + float(phase)
    )

    blob.method = "STL"
    blob.coefficients = {
        "period": float(period),
        "amplitude": float(amplitude),
        "phase": float(phase),
    }
    blob.components = {
        "trend": np.full(n, level, dtype=np.float64),
        "seasonal": seasonal,
        "residual": np.zeros(n, dtype=np.float64),
    }
    blob.residual = np.zeros(n, dtype=np.float64)

    return Tier2OpResult(
        values=blob.reassemble(),
        relabel=_deterministic("cycle"),
        op_name="replace_with_cycle",
    )


# ---------------------------------------------------------------------------
# tilt_detrend
# ---------------------------------------------------------------------------


def tilt_detrend(
    blob: DecompositionBlob,
    beta_local: float,
    t: np.ndarray,
    pre_shape: str = "plateau",
) -> Tier2OpResult:
    """Remove a local linear drift from a near-plateau segment.

    Subtracts a fitted linear component from the reassembled signal:
        result(t) = signal(t) - beta_local * (t - t[0])

    When beta_local equals the OLS slope of the signal, the residual has
    near-zero local slope, restoring plateau character.  The blob is not
    mutated.

    Relabeling: PRESERVED('plateau') — drift removal restores plateau shape.

    Reference: Cleveland et al. (1990) — residual structure after detrending.

    Args:
        blob:        Constant-method DecompositionBlob.
        beta_local:  Estimated local drift slope (value units per time step).
        t:           Time axis for the segment, shape (n,).
        pre_shape:   Shape label before the edit.

    Returns:
        Tier2OpResult with detrended values and PRESERVED relabeling.
    """
    t_arr = np.asarray(t, dtype=np.float64)
    signal = blob.reassemble()
    detrended = signal - float(beta_local) * (t_arr - t_arr[0])
    return Tier2OpResult(
        values=detrended,
        relabel=_preserved(pre_shape),
        op_name="tilt_detrend",
    )
