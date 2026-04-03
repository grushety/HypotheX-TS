"""Uncertainty scoring for boundaries and segment labels (SEG-004).

Provides ``score_uncertainty(values, segments, boundary_scores)`` which returns
per-timestep boundary uncertainty and per-segment label uncertainty.

Boundary uncertainty ``u_t``:
  The raw boundary score array (already in [0, 1] from the proposer) is
  smoothed with a 1-D Gaussian kernel (σ = 2.0) so that uncertainty is
  diffuse around each proposed boundary rather than concentrated at a single
  timestep.  Outside boundary neighbourhoods the smoothed value is near-zero.

  Source: Gaussian kernel density estimation — standard smoothing technique;
  kernel construction follows Bishop (2006) §2.5.1.

Segment label uncertainty ``u_k``:
  Shannon entropy of the label probability distribution normalised to [0, 1]
  by dividing by log(|Y|) where |Y| is the number of active labels:

      u_k = H(p(y | s)) / log(|Y|)
          = -( Σ_y p_y * log(p_y) ) / log(|Y|)

  A value of 0 means the classifier is completely certain; 1 means the
  distribution is completely uniform over all labels.

  Source: Shannon, C. E. (1948). "A Mathematical Theory of Communication",
  Bell System Technical Journal 27(3), pp. 379–423.  Normalised form from
  MacKay (2003) §2.1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.services.suggestion.boundary_proposal import ProvisionalSegment


class UncertaintyError(RuntimeError):
    """Raised when uncertainty cannot be computed safely."""


@dataclass(frozen=True)
class UncertaintyResult:
    """Per-timestep boundary uncertainty and per-segment label uncertainty.

    Attributes:
        boundary_uncertainty: Length T.  Each value in [0, 1]; high values
            indicate the model is uncertain about whether a boundary exists
            at that timestep.
        segment_uncertainty:  Length K (one per segment).  Each value in
            [0, 1]; 0 = certain prediction, 1 = maximally uncertain.
    """

    boundary_uncertainty: tuple[float, ...]
    segment_uncertainty: tuple[float, ...]


def score_uncertainty(
    values: np.ndarray | list,
    segments: tuple[ProvisionalSegment, ...] | list[ProvisionalSegment],
    boundary_scores: np.ndarray,
    *,
    sigma: float = 2.0,
) -> UncertaintyResult:
    """Compute boundary and label uncertainty for a segmented series.

    Args:
        values:          Original series (1-D list or array) — used only to
                         validate that boundary_scores has the correct length.
        segments:        Provisional segments produced by the boundary proposer,
                         each optionally carrying a ``labelScores`` dict.
        boundary_scores: Raw boundary score array of shape ``(T,)`` as returned
                         by ``compute_boundary_scores``.  Values should be in
                         [0, 1] (the proposer normalises them).
        sigma:           Standard deviation of the Gaussian smoothing kernel
                         (default 2.0 timesteps).

    Returns:
        UncertaintyResult with ``boundary_uncertainty`` of length T and
        ``segment_uncertainty`` of length K.

    Raises:
        UncertaintyError: If boundary_scores length does not match the series.
    """
    scores_arr = np.asarray(boundary_scores, dtype=np.float64)
    if scores_arr.ndim != 1:
        raise UncertaintyError("boundary_scores must be a 1-D array.")

    # Infer series length from values (same convention as normalize_series:
    # (C, T) where C ≤ T — so series_length = shape[-1] for 2-D inputs).
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim == 1:
        series_len = int(arr.shape[0])
    elif arr.ndim == 2:
        # Follows normalize_series: if rows > cols it's (T, C), else (C, T).
        series_len = int(arr.shape[0]) if arr.shape[0] > arr.shape[1] else int(arr.shape[1])
    else:
        raise UncertaintyError("values must be 1-D or 2-D.")

    if len(scores_arr) != series_len:
        raise UncertaintyError(
            f"boundary_scores length ({len(scores_arr)}) must equal series length ({series_len})."
        )

    smoothed = _smooth_boundary_scores(scores_arr, sigma=sigma)
    seg_uncertainty = _compute_segment_uncertainty(segments)
    return UncertaintyResult(
        boundary_uncertainty=tuple(float(v) for v in smoothed),
        segment_uncertainty=seg_uncertainty,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _smooth_boundary_scores(boundary_scores: np.ndarray, sigma: float = 2.0) -> np.ndarray:
    """Gaussian-smooth a boundary score array; clipped to [0, 1].

    Uses ``np.convolve`` with ``mode='same'`` so the output length equals the
    input length.  Near-zero values outside boundary neighbourhoods are
    preserved because the raw scores are near-zero there too.

    Source: Bishop (2006) §2.5.1 — Gaussian kernel construction.
    """
    kernel = _gaussian_kernel(sigma)
    smoothed = np.convolve(boundary_scores.astype(np.float64), kernel, mode="same")
    return np.clip(smoothed, 0.0, 1.0)


def _gaussian_kernel(sigma: float, truncate: float = 4.0) -> np.ndarray:
    """Build a 1-D Gaussian kernel normalised to sum to 1.

    The kernel is truncated at ``truncate * sigma`` timesteps on each side.
    Minimum radius is 1 so the kernel has at least 3 elements.

    Args:
        sigma:    Standard deviation in timesteps.
        truncate: Truncation factor (default 4.0 — effectively lossless).

    Returns:
        np.ndarray of odd length; sums to 1.
    """
    radius = max(1, int(truncate * sigma + 0.5))
    t = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-0.5 * (t / sigma) ** 2)
    return kernel / kernel.sum()


def _compute_segment_uncertainty(
    segments: tuple[ProvisionalSegment, ...] | list[ProvisionalSegment],
) -> tuple[float, ...]:
    """Return normalised entropy for each segment's label distribution.

    Segments without ``labelScores`` get an uncertainty of 0.0 (no
    distributional information available → treat as certain).
    """
    return tuple(_normalized_entropy(seg.labelScores or {}) for seg in segments)


def _normalized_entropy(probabilities: dict[str, float]) -> float:
    """Compute H(p) / log(|Y|) — normalised Shannon entropy in [0, 1].

    Returns 0.0 when ``probabilities`` is empty or contains only one label
    (log(1) == 0 would cause division by zero — but zero spread means zero
    uncertainty anyway).

    Source: Shannon (1948); normalisation from MacKay (2003) §2.1.
    """
    n = len(probabilities)
    if n <= 1:
        return 0.0
    log_n = math.log(n)
    raw_entropy = sum(-p * math.log(p) for p in probabilities.values() if p > 1e-15)
    return float(min(1.0, raw_entropy / log_n))
