"""Linear-time MMD distributional-shift test for replace_from_library (VAL-008).

Detects whether a donor-based replacement (Native Guide, SETS, Discord,
TimeGAN — the OP-012 backends) introduces a distributional shift relative
to the rest of the user's series. Linear-time MMD² (Gretton et al. 2012
Theorem 6) keeps the test in the 200 ms budget on series up to ~10 k
samples; the block-permutation null preserves autocorrelation via the
Politis-Romano stationary bootstrap (1994).

Sources (binding for ``algorithm-auditor``):

  - Gretton, Borgwardt, Rasch, Schölkopf, Smola, "A Kernel Two-Sample
    Test," *JMLR* 13:723 (2012). Theorem 6 = linear-time MMD² estimator
    (this module's main statistic).
  - Lloyd & Ghahramani, "Statistical Model Criticism using Kernel
    Two-Sample Tests," NeurIPS 2015 — block-permutation null calibration.
  - Politis & Romano, *JASA* 89:1303 (1994) — stationary bootstrap (re-used
    from VAL-005's helper module).

Whitening contract (load-bearing per AC).
The AC requires this validator to run on **whitened residuals**, not the
raw signal — distributional shift on coloured / autocorrelated input is
swamped by the temporal structure. Whitening is the *caller's*
responsibility; the validator does not detect or enforce it. Callers
should pre-whiten via ``app.services.validation.stationarity.whiten_residual``
before passing arrays in, and the public functions document this loudly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from app.services.validation.coefficient_ci import (
    politis_white_block_length,
    stationary_bootstrap,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MMDDistShiftError(RuntimeError):
    """Raised when the linear-time MMD inputs are unusable."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


KERNEL_RBF_MEDIAN = "rbf_median"
_ALLOWED_KERNELS = frozenset({KERNEL_RBF_MEDIAN})

DEFAULT_PERMUTATIONS = 200
_VAR_FLOOR = 1e-12  # avoid div/0 on degenerate (constant) inputs


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MMDLinearResult:
    """Linear-time MMD² estimate (Gretton 2012 Theorem 6).

    Attributes:
        mmd2:      Empirical MMD² (mean of the per-pair h statistic).
        std_err:   √(Var[h] / N) — asymptotic standard error of the mean.
        z_score:   ``mmd2 / max(std_err, √_VAR_FLOOR)``; the asymptotic
                   normal test statistic under the null.
        bandwidth: RBF bandwidth used (median-heuristic on concatenated
                   sample).
        n_pairs:   Number of (X-pair, Y-pair) units used in h; equals
                   ``min(len(X), len(Y)) // 2``.
    """

    mmd2: float
    std_err: float
    z_score: float
    bandwidth: float
    n_pairs: int


@dataclass(frozen=True)
class DistShiftResult:
    """Block-permutation-calibrated distributional-shift test."""

    mmd2: float
    std_err: float
    z_score: float
    p_value: float
    bandwidth: float
    n_pairs: int
    n_permutations: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _flatten(name: str, arr: np.ndarray | Sequence[float]) -> np.ndarray:
    a = np.atleast_1d(np.asarray(arr, dtype=np.float64)).reshape(-1)
    if a.size == 0:
        raise MMDDistShiftError(f"{name} must be non-empty")
    return a


def _median_heuristic_bandwidth(values: np.ndarray) -> float:
    """Median of pairwise |x_i − x_j| on the concatenated sample.

    Falls back to 1.0 on degenerate (constant) input so the RBF kernel
    stays well-defined. Random subsampling (cap=500) keeps the n²
    pairwise calculation tractable on long series.
    """
    flat = values.reshape(-1)
    n = flat.size
    if n < 2:
        return 1.0
    cap = 500
    if n > cap:
        # Deterministic-by-index draw — caller's RNG seed is for sampling, not
        # bandwidth choice. The median is invariant under a stable subsample.
        idx = np.linspace(0, n - 1, cap, dtype=int)
        flat = flat[idx]
        n = flat.size
    diff = np.abs(flat[:, None] - flat[None, :])
    iu = np.triu_indices(n, k=1)
    pair = diff[iu]
    if pair.size == 0:
        return 1.0
    med = float(np.median(pair))
    return med if med > 0.0 else 1.0


def _rbf_pair(u: np.ndarray, v: np.ndarray, bandwidth: float) -> np.ndarray:
    """Element-wise RBF kernel on aligned 1-D vectors."""
    diff = u - v
    return np.exp(-(diff * diff) / (2.0 * bandwidth * bandwidth))


# ---------------------------------------------------------------------------
# Linear-time MMD² (Gretton 2012 Theorem 6)
# ---------------------------------------------------------------------------


def mmd_linear_time(
    X: np.ndarray | Sequence[float],
    Y: np.ndarray | Sequence[float],
    *,
    kernel: str = KERNEL_RBF_MEDIAN,
    bandwidth: float | None = None,
) -> MMDLinearResult:
    """Linear-time MMD² estimator on whitened residuals.

    For ``N = min(len(X), len(Y)) // 2`` pairs of samples,

        h_i = k(X_{2i}, X_{2i+1}) + k(Y_{2i}, Y_{2i+1})
              − k(X_{2i}, Y_{2i+1}) − k(X_{2i+1}, Y_{2i})

    is an unbiased single-pair estimator of MMD²; their mean is the
    Gretton 2012 Theorem 6 estimator and Var[h]/N is the asymptotic
    variance. RBF kernel with median-heuristic bandwidth (computed from
    the concatenated sample) is the default. Inputs of unequal length
    are trimmed to ``min(len(X), len(Y))``.

    Args:
        X, Y:      1-D **whitened residual** arrays. Whitening is the
                   caller's responsibility — the validator does not
                   enforce it (see module docstring).
        kernel:    Currently only ``'rbf_median'`` is supported.
        bandwidth: Override the median-heuristic σ. Defaults to ``None``.

    Returns:
        ``MMDLinearResult`` with mmd², std_err, z-score, bandwidth, n_pairs.

    Raises:
        ``MMDDistShiftError`` on empty inputs, unsupported kernel, or
        too few pairs (need ≥ 1 pair, i.e. each input ≥ 2 samples).
    """
    if kernel not in _ALLOWED_KERNELS:
        raise MMDDistShiftError(
            f"kernel must be one of {sorted(_ALLOWED_KERNELS)}; got {kernel!r}"
        )
    x = _flatten("X", X)
    y = _flatten("Y", Y)
    n_total = min(x.size, y.size)
    n_pairs = n_total // 2
    if n_pairs < 1:
        raise MMDDistShiftError(
            f"linear-time MMD requires ≥ 2 samples per side; got X={x.size}, Y={y.size}"
        )
    x = x[: 2 * n_pairs]
    y = y[: 2 * n_pairs]

    sigma = (
        float(bandwidth) if bandwidth is not None
        else _median_heuristic_bandwidth(np.concatenate([x, y]))
    )
    if sigma <= 0:
        raise MMDDistShiftError(f"bandwidth must be > 0; got {sigma}")

    # Vectorised h_i for i = 0..n_pairs-1
    x_a, x_b = x[0::2], x[1::2]
    y_a, y_b = y[0::2], y[1::2]
    h = (
        _rbf_pair(x_a, x_b, sigma)
        + _rbf_pair(y_a, y_b, sigma)
        - _rbf_pair(x_a, y_b, sigma)
        - _rbf_pair(x_b, y_a, sigma)
    )
    mmd2 = float(h.mean())
    var = float(h.var(ddof=0)) / max(n_pairs, 1)
    std_err = float(np.sqrt(max(var, 0.0)))
    z_score = mmd2 / max(std_err, np.sqrt(_VAR_FLOOR))

    return MMDLinearResult(
        mmd2=mmd2,
        std_err=std_err,
        z_score=float(z_score),
        bandwidth=float(sigma),
        n_pairs=int(n_pairs),
    )


# ---------------------------------------------------------------------------
# Quadratic MMD (for the linear-vs-quadratic agreement test only)
# ---------------------------------------------------------------------------


def mmd_quadratic(
    X: np.ndarray | Sequence[float],
    Y: np.ndarray | Sequence[float],
    *,
    bandwidth: float | None = None,
) -> float:
    """Biased quadratic MMD² estimator — used only for the linear/quadratic
    agreement test in VAL-008's test suite.

        mmd² = mean(K_pp) + mean(K_qq) − 2·mean(K_pq)

    O(n_X · n_Y) memory; not meant for the hot path.
    """
    x = _flatten("X", X)
    y = _flatten("Y", Y)
    sigma = (
        float(bandwidth) if bandwidth is not None
        else _median_heuristic_bandwidth(np.concatenate([x, y]))
    )
    if sigma <= 0:
        raise MMDDistShiftError(f"bandwidth must be > 0; got {sigma}")

    def _km(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        d = a[:, None] - b[None, :]
        return np.exp(-(d * d) / (2.0 * sigma * sigma))

    return float(_km(x, x).mean() + _km(y, y).mean() - 2.0 * _km(x, y).mean())


# ---------------------------------------------------------------------------
# Block-permutation distshift (the public per-OP-012 entry point)
# ---------------------------------------------------------------------------


def replace_library_distshift(
    window_post: np.ndarray | Sequence[float],
    context: np.ndarray | Sequence[float],
    *,
    n_permutations: int = DEFAULT_PERMUTATIONS,
    kernel: str = KERNEL_RBF_MEDIAN,
    rng: np.random.Generator | None = None,
    block_length: int | None = None,
) -> DistShiftResult:
    """Block-permutation-calibrated linear-time MMD² distributional-shift
    test for OP-012's donor-replaced window vs the surrounding context.

    Pipeline:
      1. Compute the observed linear-time MMD² between ``window_post``
         and ``context`` (median-heuristic bandwidth on the concatenated
         pair).
      2. Pool the two and resample via stationary bootstrap (block length
         from Politis-White on the pooled series, or caller-supplied)
         ``n_permutations`` times. The first ``len(window_post)`` of each
         permutation become the synthetic "window", the rest the
         synthetic "context"; recompute the linear-time MMD² for each.
      3. p-value = ``(1 + #{perm_mmd² ≥ observed}) / (1 + B)`` — the
         standard plus-one correction so an observed-only-tied count
         maps to ``1/(B+1)`` rather than 0.

    Args:
        window_post:    1-D **whitened** residual of the donor-replaced window.
        context:        1-D **whitened** residual of the surrounding context.
        n_permutations: Permutation null sample count; default 200.
        kernel:         Currently only ``'rbf_median'``.
        rng:            Optional ``np.random.Generator`` for reproducibility.
        block_length:   Override stationary-bootstrap block length;
                        ``None`` triggers Politis-White on the pooled series.

    Returns:
        ``DistShiftResult`` carrying the observed mmd², std_err, z-score,
        permutation p-value, bandwidth, n_pairs, n_permutations.
    """
    if n_permutations < 2:
        raise ValueError(f"n_permutations must be ≥ 2; got {n_permutations}")
    if kernel not in _ALLOWED_KERNELS:
        raise MMDDistShiftError(
            f"kernel must be one of {sorted(_ALLOWED_KERNELS)}; got {kernel!r}"
        )

    window = _flatten("window_post", window_post)
    ctx = _flatten("context", context)
    if window.size < 2 or ctx.size < 2:
        raise MMDDistShiftError(
            f"distshift test requires ≥ 2 samples per side; "
            f"got window={window.size}, context={ctx.size}"
        )

    generator = rng if rng is not None else np.random.default_rng()

    observed = mmd_linear_time(window, ctx, kernel=kernel)

    pooled = np.concatenate([window, ctx])
    bl = block_length if block_length is not None else politis_white_block_length(pooled)
    n_window = window.size

    perm_count = 0
    for _ in range(n_permutations):
        perm = stationary_bootstrap(pooled, bl, rng=generator)
        a = perm[:n_window]
        b = perm[n_window:]
        # Skip degenerate splits (shouldn't happen — pooled is long enough)
        if a.size < 2 or b.size < 2:
            continue
        perm_mmd = mmd_linear_time(a, b, kernel=kernel, bandwidth=observed.bandwidth)
        if perm_mmd.mmd2 >= observed.mmd2:
            perm_count += 1

    p_value = (1 + perm_count) / (1 + n_permutations)
    return DistShiftResult(
        mmd2=observed.mmd2,
        std_err=observed.std_err,
        z_score=observed.z_score,
        p_value=float(p_value),
        bandwidth=observed.bandwidth,
        n_pairs=observed.n_pairs,
        n_permutations=int(n_permutations),
    )
