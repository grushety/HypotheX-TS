"""Tier-2 spike ops: remove, clip_cap, amplify, smear_to_transient,
duplicate, shift_time (OP-023).

Spike ops work on raw signal values (X_seg: np.ndarray) — spikes are
residual outliers without a parametric decomposition coefficient to edit.

Relabeling:
  remove                → RECLASSIFY_VIA_SEGMENTER
  clip_cap              → PRESERVED('spike')
  amplify               → PRESERVED('spike')
  smear_to_transient    → DETERMINISTIC('transient')
  duplicate             → RECLASSIFY_VIA_SEGMENTER  (multi-spike split hint)
  shift_time            → PRESERVED('spike')

References
----------
Hampel (1974) "The influence curve and its role in robust estimation"
    JASA 69(346):383-393.
    → remove (hampel): sliding-window median ± n_sigma × 1.4826 × MAD.

Chen, Jönsson, Tamura, Gu, Matsushita, Eklundh (2004) "A simple method for
    reconstructing a high-quality NDVI time series data set based on the
    Savitzky-Golay filter" Remote Sensing of Environment 91(3-4):332-344.
    → remove (chen_sg): iterative SG-envelope spike replacement.

Ricker (1943) "Further developments in the wavelet theory of seismogram
    structure" BSSA 33(3):197-228.
    → smear_to_transient: Ricker wavelet convolution to produce transient shape.
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np

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


def _reclassify(pre_shape: str) -> RelabelResult:
    return RelabelResult(
        new_shape=pre_shape,
        confidence=0.0,
        needs_resegment=True,
        rule_class="RECLASSIFY_VIA_SEGMENTER",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sg_window_length(n: int) -> int:
    """Largest odd window ≤ n satisfying SG polyorder=3 (needs window ≥ 4)."""
    w = min(11, n)
    if w < 4:
        return max(1, w | 1)
    return w if w % 2 == 1 else w - 1


def _ricker_wavelet(points: int, a: float) -> np.ndarray:
    """Ricker (Mexican hat) wavelet.

    Reference: Ricker (1943) BSSA 33(3):197-228. Formula matches the historical
    scipy.signal.ricker implementation (removed in scipy >= 1.12).
    """
    A = 2.0 / (np.sqrt(3.0 * a) * (np.pi ** 0.25))
    wsq = float(a) ** 2
    vec = np.arange(points, dtype=np.float64) - (points - 1.0) / 2.0
    return A * (1.0 - vec ** 2 / wsq) * np.exp(-vec ** 2 / (2.0 * wsq))


def _hampel_filter(X: np.ndarray, window: int = 7, n_sigma: float = 3.0) -> np.ndarray:
    """Offline Hampel identifier: replace outliers with window median.

    Uses the original (un-modified) signal for all window lookups so that
    a replaced sample does not influence neighbouring decisions.

    Reference: Hampel (1974) JASA 69(346):383-393 — threshold = n_sigma × 1.4826 × MAD
    (scale factor 1.4826 gives Gaussian-consistency for MAD).
    """
    orig = X.copy()
    result = X.copy()
    k = window // 2
    n = len(orig)
    for i in range(n):
        lo = max(0, i - k)
        hi = min(n, i + k + 1)
        win = orig[lo:hi]
        med = float(np.median(win))
        mad = float(np.median(np.abs(win - med)))
        threshold = n_sigma * 1.4826 * mad
        if np.abs(orig[i] - med) > threshold:
            result[i] = med
    return result


def _chen_sg(X: np.ndarray, n_iter: int = 3, n_sigma: float = 3.0) -> np.ndarray:
    """Iterative SG-envelope spike removal.

    Reference: Chen et al. (2004) RSE 91(3-4):332-344 — iterative SG fitting;
    adapted for spike removal: samples deviating > n_sigma × σ from the SG
    fit are replaced by the SG fitted value.
    """
    from scipy.signal import savgol_filter  # noqa: PLC0415

    arr = X.copy()
    n = len(arr)
    wl = _sg_window_length(n)
    for _ in range(n_iter):
        if wl >= 4:
            fitted = savgol_filter(arr, window_length=wl, polyorder=3)
        else:
            fitted = arr.copy()
        residuals = arr - fitted
        sigma = float(np.std(residuals))
        if sigma < 1e-12:
            break
        spikes = np.abs(residuals) > n_sigma * sigma
        arr[spikes] = fitted[spikes]
    return arr


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------


def remove(
    X_seg: np.ndarray,
    method: Literal["hampel", "chen_sg"] = "hampel",
    pre_shape: str = "spike",
) -> Tier2OpResult:
    """Remove spike(s) by replacing outliers with a local baseline estimate.

    Two methods:
      'hampel' (default) — Hampel identifier: sliding-window median ± n_sigma MAD.
          Reference: Hampel (1974) JASA 69(346):383-393.
      'chen_sg' — Iterative SG-envelope spike replacement.
          Reference: Chen et al. (2004) RSE 91(3-4):332-344.

    Relabeling: RECLASSIFY_VIA_SEGMENTER — the post-removal shape depends on
    the residual signal.

    Args:
        X_seg:     Spike segment values, shape (n,).
        method:    Removal method: 'hampel' or 'chen_sg'.
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with de-spiked values and RECLASSIFY relabeling.

    Raises:
        ValueError: If method is not 'hampel' or 'chen_sg'.
    """
    if method not in ("hampel", "chen_sg"):
        raise ValueError(
            f"remove: unknown method '{method}'. Choose 'hampel' or 'chen_sg'."
        )
    arr = np.asarray(X_seg, dtype=np.float64)
    values = _hampel_filter(arr) if method == "hampel" else _chen_sg(arr)
    return Tier2OpResult(
        values=values,
        relabel=_reclassify(pre_shape),
        op_name="remove",
    )


# ---------------------------------------------------------------------------
# clip_cap
# ---------------------------------------------------------------------------


def clip_cap(
    X_seg: np.ndarray,
    quantile: float = 0.99,
    pre_shape: str = "spike",
) -> Tier2OpResult:
    """Winsorize the segment by capping values at the given upper quantile.

    Values above `np.quantile(X_seg, quantile)` are replaced by the cap value.
    Values at or below the cap are unchanged (one-sided winsorization for
    positive spikes). To cap negative spikes, negate the signal first.

    Reference: Winsorization — standard robust statistics; np.minimum(X, cap)
    as in the pseudocode.

    Args:
        X_seg:     Segment values, shape (n,).
        quantile:  Upper quantile for the cap in (0, 1].
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with clipped values and PRESERVED('spike') relabeling.

    Raises:
        ValueError: If quantile is outside (0, 1].
    """
    if not (0.0 < float(quantile) <= 1.0):
        raise ValueError(f"clip_cap: quantile must be in (0, 1], got {quantile!r}.")
    arr = np.asarray(X_seg, dtype=np.float64)
    cap = float(np.quantile(arr, quantile))
    return Tier2OpResult(
        values=np.minimum(arr, cap),
        relabel=_preserved(pre_shape),
        op_name="clip_cap",
    )


# ---------------------------------------------------------------------------
# amplify
# ---------------------------------------------------------------------------


def amplify(
    X_seg: np.ndarray,
    t_peak: int,
    alpha: float,
    widening_sigma: float = 2.0,
    pre_shape: str = "spike",
) -> Tier2OpResult:
    """Scale a spike by alpha with a Gaussian spatial envelope centred at t_peak.

    output[i] = X[i] * (1 + w[i] * (alpha − 1))
    where w[i] = exp(−0.5 × ((i − t_peak) / widening_sigma)²).

    At i == t_peak: w = 1, so output[t_peak] = alpha × X[t_peak].
    Far from t_peak: w → 0, output[i] → X[i] (identity).

    widening_sigma controls the spatial extent: larger σ spreads the scaling
    further from the peak, smaller σ confines it to the immediate vicinity.

    Args:
        X_seg:          Segment values, shape (n,).
        t_peak:         Index of the spike peak (0-based).
        alpha:          Scale factor at peak (alpha=1 → identity; alpha=0 → zeros peak).
        widening_sigma: Standard deviation of the Gaussian envelope in samples.
        pre_shape:      Shape label before the edit.

    Returns:
        Tier2OpResult with scaled values and PRESERVED('spike') relabeling.

    Raises:
        ValueError: If widening_sigma <= 0 or t_peak is out of range.
    """
    arr = np.asarray(X_seg, dtype=np.float64)
    n = len(arr)
    if not (0 <= int(t_peak) < n):
        raise ValueError(f"amplify: t_peak={t_peak} out of range [0, {n - 1}].")
    if float(widening_sigma) <= 0.0:
        raise ValueError(
            f"amplify: widening_sigma must be > 0, got {widening_sigma!r}."
        )
    idx = np.arange(n, dtype=np.float64)
    w = np.exp(-0.5 * ((idx - float(t_peak)) / float(widening_sigma)) ** 2)
    values = arr + w * (float(alpha) - 1.0) * arr
    return Tier2OpResult(
        values=values,
        relabel=_preserved(pre_shape),
        op_name="amplify",
    )


# ---------------------------------------------------------------------------
# smear_to_transient
# ---------------------------------------------------------------------------


def smear_to_transient(
    X_seg: np.ndarray,
    sigma_new: float,
    pre_shape: str = "spike",
) -> Tier2OpResult:
    """Convolve the spike with a Ricker wavelet to smear it into a transient shape.

    The spike is convolved with a Ricker (Mexican hat) wavelet of width sigma_new,
    spreading the instantaneous impulse into a smooth bell-shaped excursion. The
    kernel is L1-normalised before convolution to preserve approximate amplitude.

    Reference: Ricker (1943) BSSA 33(3):197-228 — wavelet basis for seismogram
    structure; scipy.signal.ricker formula (removed in scipy >= 1.12, implemented
    here directly).

    Args:
        X_seg:     Segment values, shape (n,).
        sigma_new: Width of the Ricker wavelet in samples (> 0).
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with smeared values and DETERMINISTIC('transient').

    Raises:
        ValueError: If sigma_new <= 0.
    """
    if float(sigma_new) <= 0.0:
        raise ValueError(
            f"smear_to_transient: sigma_new must be > 0, got {sigma_new!r}."
        )
    arr = np.asarray(X_seg, dtype=np.float64)
    points = max(5, int(6 * float(sigma_new)))
    if points % 2 == 0:
        points += 1
    kernel = _ricker_wavelet(points, float(sigma_new))
    l1 = float(np.sum(np.abs(kernel)))
    if l1 > 1e-12:
        kernel = kernel / l1
    values = np.convolve(arr, kernel, mode="same")
    return Tier2OpResult(
        values=values,
        relabel=_deterministic("transient"),
        op_name="smear_to_transient",
    )


# ---------------------------------------------------------------------------
# duplicate
# ---------------------------------------------------------------------------


def duplicate(
    X_seg: np.ndarray,
    t_new: int,
    alpha: float,
    pre_shape: str = "spike",
) -> Tier2OpResult:
    """Add a second spike at sample t_new with amplitude alpha × original peak.

    The original peak position is found automatically via argmax(|X_seg|).
    The duplicate is added additively at t_new.

    Two spikes within one segment suggest the segment should be split; the
    relabeling signals RECLASSIFY_VIA_SEGMENTER to prompt re-segmentation.

    Args:
        X_seg:     Segment values, shape (n,).
        t_new:     Target sample index for the duplicate (0-based).
        alpha:     Amplitude scale relative to the original peak value.
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with two-spike values and RECLASSIFY relabeling.

    Raises:
        ValueError: If t_new is out of range.
    """
    arr = np.asarray(X_seg, dtype=np.float64)
    n = len(arr)
    if not (0 <= int(t_new) < n):
        raise ValueError(f"duplicate: t_new={t_new} out of range [0, {n - 1}].")
    t_peak = int(np.argmax(np.abs(arr)))
    delta = np.zeros(n, dtype=np.float64)
    delta[int(t_new)] = float(alpha) * arr[t_peak]
    return Tier2OpResult(
        values=arr + delta,
        relabel=_reclassify(pre_shape),
        op_name="duplicate",
    )


# ---------------------------------------------------------------------------
# shift_time
# ---------------------------------------------------------------------------


def shift_time(
    X_seg: np.ndarray,
    delta_t: int,
    pre_shape: str = "spike",
) -> Tier2OpResult:
    """Shift the spike position by delta_t samples (circular, with edge tapering).

    Delegates to the Tier-1 time_shift atom (OP-011). Positive delta_t moves
    the spike forward (later in time); negative moves it backward.

    Relabeling: PRESERVED('spike') — relocation does not change shape class.

    Reference: Oppenheim & Schafer (2010) Discrete-Time Signal Processing
    Ch. 4 — circular shift with tapered edge (np.roll + linear ramp).

    Args:
        X_seg:     Segment values, shape (n,).
        delta_t:   Integer shift in samples.
        pre_shape: Shape label before the edit.

    Returns:
        Tier2OpResult with shifted values and PRESERVED('spike') relabeling.
    """
    from app.services.operations.tier1.time import time_shift as _time_shift  # noqa: PLC0415

    arr = np.asarray(X_seg, dtype=np.float64)
    taper_width = max(1, min(5, len(arr) - 1))
    tier1_result = _time_shift(arr, int(delta_t), taper_width=taper_width, pre_shape=pre_shape)
    return Tier2OpResult(
        values=tier1_result.values,
        relabel=_preserved(pre_shape),
        op_name="shift_time",
    )
