"""Tier-1 time-axis atoms: time_shift, reverse_time, resample (OP-011).

Three label-agnostic time-axis operations applicable to any segment.
Unlike amplitude atoms (OP-010), these operate on raw values only — there is
no clean decomposition-coefficient analogue for time-axis manipulation.

Sources:
    Savitzky & Golay (1964) "Smoothing and differentiation of data by
    simplified least squares procedures", Anal. Chem. 36(8):1627-1639
    (SG filter used in the 'sg' resample path).

    Oppenheim & Schafer (2010) "Discrete-Time Signal Processing" 3rd ed.,
    Ch. 4 — anti-aliasing: low-pass filter must be applied BEFORE
    subsampling to avoid spectral aliasing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.services.operations.relabeler.relabeler import RelabelResult


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class TimeOpResult:
    """Result of a Tier-1 time-axis operation.

    Attributes:
        values:  Edited segment values (numpy array).
        op_name: Operation name for audit emission (OP-041).
        relabel: Always PRESERVED — time-axis manipulation does not change shape.
        tier:    Always 1 for time atoms.
    """

    values: np.ndarray
    op_name: str
    relabel: RelabelResult
    tier: int = 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _preserved(pre_shape: str) -> RelabelResult:
    return RelabelResult(
        new_shape=pre_shape,
        confidence=1.0,
        needs_resegment=False,
        rule_class="PRESERVED",
    )


def _sg_window_length(n: int) -> int:
    """Largest odd window ≤ n satisfying the SG polyorder=3 requirement (window ≥ 4)."""
    w = min(11, n)
    if w < 4:
        return max(1, w | 1)
    return w if w % 2 == 1 else w - 1


# ---------------------------------------------------------------------------
# Public ops
# ---------------------------------------------------------------------------


def time_shift(
    X_seg: np.ndarray,
    delta_t: int,
    taper_width: int = 5,
    pre_shape: str = "unknown",
) -> TimeOpResult:
    """Shift a segment forward or backward in time (circular, with edge tapering).

    Uses np.roll to perform a circular shift, then tapers the wrap-around edges
    with a linear ramp to avoid a spurious discontinuity at the boundary.

    Args:
        X_seg:       Segment signal, shape (n,).
        delta_t:     Integer shift in samples. Positive → shift right; negative → left.
        taper_width: Width of the linear taper applied to wrap-around edges.
        pre_shape:   Shape label before the edit, for relabeling.

    Returns:
        TimeOpResult with edited values (same length as X_seg).

    Raises:
        ValueError: taper_width < 1 or taper_width >= len(X_seg).
    """
    arr = np.asarray(X_seg, dtype=np.float64)
    n = len(arr)

    if delta_t == 0:
        return TimeOpResult(values=arr.copy(), op_name="time_shift", relabel=_preserved(pre_shape))

    if taper_width < 1:
        raise ValueError(f"time_shift: taper_width must be >= 1, got {taper_width}.")
    if taper_width >= n:
        raise ValueError(
            f"time_shift: taper_width ({taper_width}) must be < signal length ({n})."
        )

    shifted = np.roll(arr, delta_t)
    w = np.linspace(0, 1, taper_width)

    if delta_t > 0:
        ref = shifted[taper_width]
        shifted[:taper_width] = w * shifted[:taper_width] + (1.0 - w) * ref
    else:
        ref = shifted[-taper_width - 1]
        shifted[-taper_width:] = (1.0 - w) * shifted[-taper_width:] + w * ref

    return TimeOpResult(values=shifted, op_name="time_shift", relabel=_preserved(pre_shape))


def reverse_time(
    X_seg: np.ndarray,
    pre_shape: str = "unknown",
) -> TimeOpResult:
    """Reverse the time axis of a segment.

    Involutive: reverse_time(reverse_time(X)) == X exactly.

    Args:
        X_seg:     Segment signal, shape (n,).
        pre_shape: Shape label before the edit, for relabeling.

    Returns:
        TimeOpResult with time-reversed values.
    """
    arr = np.asarray(X_seg, dtype=np.float64)
    return TimeOpResult(
        values=arr[::-1].copy(),
        op_name="reverse_time",
        relabel=_preserved(pre_shape),
    )


def resample(
    X_seg: np.ndarray,
    new_dt: float,
    old_dt: float = 1.0,
    method: Literal["antialiased", "sg", "linear"] = "antialiased",
    pre_shape: str = "unknown",
) -> TimeOpResult:
    """Resample a segment to a new time step.

    Three methods:
      'antialiased' (default) — scipy decimate (FIR LPF before decimation,
          Oppenheim Ch. 4) for downsampling; resample_poly for upsampling.
      'sg' — Savitzky-Golay smoothing then linear interpolation.
      'linear' — raw linear interpolation (no anti-aliasing).

    Args:
        X_seg:     Segment signal, shape (n,).
        new_dt:    Target sample interval (must be > 0).
        old_dt:    Original sample interval (must be > 0).
        method:    Resampling method.
        pre_shape: Shape label before the edit, for relabeling.

    Returns:
        TimeOpResult with resampled values (length may differ from input).

    Raises:
        ValueError: new_dt or old_dt <= 0, or unknown method.
    """
    if new_dt <= 0:
        raise ValueError(f"resample: new_dt must be > 0, got {new_dt}.")
    if old_dt <= 0:
        raise ValueError(f"resample: old_dt must be > 0, got {old_dt}.")
    if method not in ("antialiased", "sg", "linear"):
        raise ValueError(
            f"resample: unknown method '{method}'. Choose 'antialiased', 'sg', or 'linear'."
        )

    arr = np.asarray(X_seg, dtype=np.float64)
    ratio = old_dt / new_dt

    if np.isclose(ratio, 1.0):
        return TimeOpResult(values=arr.copy(), op_name="resample", relabel=_preserved(pre_shape))

    if method == "antialiased":
        values = _resample_antialiased(arr, ratio)
    elif method == "sg":
        values = _resample_sg(arr, ratio)
    else:
        values = _resample_linear(arr, ratio)

    return TimeOpResult(values=values, op_name="resample", relabel=_preserved(pre_shape))


# ---------------------------------------------------------------------------
# Resample back-ends
# ---------------------------------------------------------------------------


def _resample_antialiased(arr: np.ndarray, ratio: float) -> np.ndarray:
    """Low-pass filter before decimation (Oppenheim Ch. 4 anti-aliasing).

    ratio < 1 → downsampling: apply FIR LPF then decimate.
    ratio > 1 → upsampling: use polyphase resample_poly.
    """
    from scipy.signal import decimate, resample_poly  # noqa: PLC0415

    if ratio < 1.0:
        q = max(2, int(round(1.0 / ratio)))
        return decimate(arr, q, ftype="fir", zero_phase=True)
    else:
        up = max(2, int(round(ratio)))
        return resample_poly(arr, up=up, down=1).astype(np.float64)


def _resample_sg(arr: np.ndarray, ratio: float) -> np.ndarray:
    """Savitzky-Golay smooth then linear interpolate to the new grid.

    Source: Savitzky & Golay (1964) Anal. Chem. 36(8):1627-1639.
    """
    from scipy.signal import savgol_filter  # noqa: PLC0415

    n = len(arr)
    wl = _sg_window_length(n)
    if wl >= 4:
        smoothed = savgol_filter(arr, window_length=wl, polyorder=3)
    else:
        smoothed = arr

    old_grid = np.arange(n, dtype=np.float64)
    new_grid = np.arange(0, n, 1.0 / ratio)
    return np.interp(new_grid, old_grid, smoothed)


def _resample_linear(arr: np.ndarray, ratio: float) -> np.ndarray:
    """Raw linear interpolation — no anti-aliasing."""
    n = len(arr)
    old_grid = np.arange(n, dtype=np.float64)
    new_grid = np.arange(0, n, 1.0 / ratio)
    return np.interp(new_grid, old_grid, arr)
