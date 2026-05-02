"""Conservation-residual significance battery (VAL-007).

Three jointly-run statistical tests on the conservation residual
``r_t = Σ fluxes − dStorage/dt`` produced by ``enforce_conservation``
(OP-032). Together they answer "did the projection actually close the
balance?":

  1. **Bootstrap CI** on ``E[r_post]`` under H0 ``E[r] = 0`` —
     Politis-Romano stationary bootstrap (1994); two-sided p-value.
  2. **Ratio test** ``‖r_post‖² / ‖r_pre‖²`` against an approximate
     F-reference; reports the variance reduction the projection achieved.
  3. **MMD two-sample** between ``r_pre`` and ``r_post`` distributions,
     RBF kernel with median-heuristic bandwidth, permutation null with
     B=200 (Gretton et al. 2012).

Sources (binding for ``algorithm-auditor``):

  - Beucler, Pritchard, Rasp, Ott, Baldi, Gentine,
    "Enforcing Analytic Constraints in Neural Networks Emulating Physical
    Systems," *Phys. Rev. Lett.* 126:098302 (2021),
    DOI:10.1103/PhysRevLett.126.098302.
  - Patil, Ji, Aydin, "Physics-Guided Counterfactual Explanations for
    Large-Scale Multivariate Time Series," arXiv:2601.08999 (Jan 2026).
  - Politis & Romano, *JASA* 89:1303 (1994).
  - Gretton, Borgwardt, Rasch, Schölkopf, Smola, "A Kernel Two-Sample
    Test," *JMLR* 13:723 (2012).

Patil et al. introduced physics-guided CFs but did not attach formal
p-values to conservation residuals. This module fills that gap — the
"conservation tightness" badge is a methodological contribution.

Stationary-bootstrap / block-length helpers are re-used from
``app.services.validation.coefficient_ci`` (VAL-005). MMD uses scipy.stats
for the F-reference; we never reimplement test statistics.
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


class ConservationSignificanceError(RuntimeError):
    """Raised when residual inputs are unusable (empty, mismatched, etc.)."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


DEFAULT_BOOTSTRAP_B = 999
DEFAULT_MMD_PERMUTATIONS = 200
DEFAULT_CI_QUANTILES = (0.025, 0.975)
DEFAULT_MMD_SUBSAMPLE_CAP = 500  # cap for the n² kernel matrices


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConservationConfig:
    """Configuration for the joint significance battery.

    bootstrap_B:        Number of stationary-bootstrap resamples for the
                        residual CI; default 999 (Patil et al. 2026 Tab. 2).
    mmd_permutations:   Permutation-null sample count for MMD; default 200.
    mmd_subsample_cap:  Random subsample size used for MMD kernel matrices —
                        the n² scaling makes raw 10k×10k impractical.
                        ``None`` disables subsampling.
    block_length:       Override for the stationary-bootstrap block length;
                        ``None`` triggers Politis-White auto-selection.
    ci_alpha:           Two-sided alpha for the residual CI; default 0.05.
    """

    bootstrap_B: int = DEFAULT_BOOTSTRAP_B
    mmd_permutations: int = DEFAULT_MMD_PERMUTATIONS
    mmd_subsample_cap: int | None = DEFAULT_MMD_SUBSAMPLE_CAP
    block_length: int | None = None
    ci_alpha: float = 0.05

    def __post_init__(self) -> None:
        if self.bootstrap_B < 2:
            raise ValueError(f"bootstrap_B must be ≥ 2; got {self.bootstrap_B}")
        if self.mmd_permutations < 2:
            raise ValueError(
                f"mmd_permutations must be ≥ 2; got {self.mmd_permutations}"
            )
        if self.mmd_subsample_cap is not None and self.mmd_subsample_cap < 4:
            raise ValueError(
                f"mmd_subsample_cap must be ≥ 4 or None; got {self.mmd_subsample_cap}"
            )
        if not 0.0 < self.ci_alpha < 1.0:
            raise ValueError(f"ci_alpha must be in (0, 1); got {self.ci_alpha}")
        if self.block_length is not None and self.block_length < 1:
            raise ValueError(f"block_length must be ≥ 1; got {self.block_length}")


@dataclass(frozen=True)
class ConservationCIResult:
    """Bootstrap CI on the mean conservation residual."""

    mean: float
    ci: tuple[float, float]
    p_value: float
    block_length: int
    B: int


@dataclass(frozen=True)
class RatioTestResult:
    """F-referenced variance-ratio test ``‖r_post‖² / ‖r_pre‖²``."""

    ratio: float
    f_statistic: float
    p_value: float
    df_pre: int
    df_post: int


@dataclass(frozen=True)
class MMDResult:
    """RBF-kernel MMD² two-sample test with permutation null."""

    mmd2: float
    p_value: float
    bandwidth: float
    n_permutations: int
    subsample_size: int


@dataclass(frozen=True)
class ConservationSignificance:
    """Joint outcome surfaced to UI-010 budget bar.

    Tooltip composition: ``residual_ci_post.mean ± ci`` plus
    ``ratio_test.p_value`` plus ``mmd_test.p_value``.
    """

    residual_ci_post: ConservationCIResult
    ratio_test: RatioTestResult
    mmd_test: MMDResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _flatten_residual(r: np.ndarray | Sequence[float] | float) -> np.ndarray:
    arr = np.atleast_1d(np.asarray(r, dtype=np.float64)).reshape(-1)
    return arr


def _ensure_nonempty(name: str, arr: np.ndarray) -> None:
    if arr.size == 0:
        raise ConservationSignificanceError(f"{name} must be non-empty")


# ---------------------------------------------------------------------------
# 1. Bootstrap CI on E[r] = 0
# ---------------------------------------------------------------------------


def conservation_residual_ci(
    r: np.ndarray | Sequence[float] | float,
    *,
    config: ConservationConfig | None = None,
    rng: np.random.Generator | None = None,
) -> ConservationCIResult:
    """Stationary block bootstrap CI for ``H0: E[r] = 0``.

    Returns the empirical mean of ``r``, a two-sided ``1 − ci_alpha`` CI
    on the bootstrap distribution of the mean, and a two-sided p-value
    computed as ``2 · min(P(mean ≥ 0), P(mean ≤ 0))``.

    For a constant-zero residual the bootstrap collapses to a single
    point at 0 — CI is ``(0, 0)`` and p-value is 1.0 (no evidence against H0).
    """
    cfg = config or ConservationConfig()
    arr = _flatten_residual(r)
    _ensure_nonempty("residual", arr)

    block_length = cfg.block_length if cfg.block_length is not None else \
        politis_white_block_length(arr)
    generator = rng if rng is not None else np.random.default_rng()

    means = np.empty(cfg.bootstrap_B, dtype=np.float64)
    for b in range(cfg.bootstrap_B):
        sample = stationary_bootstrap(arr, block_length, rng=generator)
        means[b] = float(np.mean(sample))

    lo_q, hi_q = cfg.ci_alpha / 2.0, 1.0 - cfg.ci_alpha / 2.0
    ci_lo = float(np.quantile(means, lo_q))
    ci_hi = float(np.quantile(means, hi_q))

    p_above = float(np.mean(means >= 0.0))
    p_below = float(np.mean(means <= 0.0))
    p_value = float(min(1.0, 2.0 * min(p_above, p_below)))

    return ConservationCIResult(
        mean=float(np.mean(arr)),
        ci=(ci_lo, ci_hi),
        p_value=p_value,
        block_length=int(block_length),
        B=int(cfg.bootstrap_B),
    )


# ---------------------------------------------------------------------------
# 2. Variance-ratio (F-referenced) test
# ---------------------------------------------------------------------------


def conservation_ratio_test(
    r_pre: np.ndarray | Sequence[float] | float,
    r_post: np.ndarray | Sequence[float] | float,
) -> RatioTestResult:
    """Wilson-style F-reference for ``‖r_post‖² / ‖r_pre‖²``.

    A successful projection drives ``r_post`` toward zero, so ``ratio < 1``
    is the desired direction; ``p_value`` is the upper-tail probability of
    seeing a ratio at least this large under the equal-variance null
    (i.e. small p ⇒ projection achieved a statistically meaningful
    reduction). Returns p_value=NaN when the pre-residual is exactly zero.
    """
    pre = _flatten_residual(r_pre)
    post = _flatten_residual(r_post)
    _ensure_nonempty("r_pre", pre)
    _ensure_nonempty("r_post", post)
    if pre.size < 2 or post.size < 2:
        raise ConservationSignificanceError(
            f"ratio test requires ≥ 2 samples per side; got pre={pre.size}, post={post.size}"
        )

    norm_sq_pre = float(np.dot(pre, pre))
    norm_sq_post = float(np.dot(post, post))
    if norm_sq_pre == 0.0:
        # Degenerate: pre-residual already exactly zero. No meaningful ratio.
        return RatioTestResult(
            ratio=float("inf") if norm_sq_post > 0 else 0.0,
            f_statistic=float("nan"),
            p_value=float("nan"),
            df_pre=pre.size - 1,
            df_post=post.size - 1,
        )

    ratio = norm_sq_post / norm_sq_pre
    df_pre = pre.size - 1
    df_post = post.size - 1
    f_stat = ratio * df_pre / max(df_post, 1)

    try:
        from scipy.stats import f as _f_dist  # noqa: PLC0415
        p_upper = float(_f_dist.sf(f_stat, df_post, df_pre))
    except Exception:  # noqa: BLE001
        p_upper = float("nan")

    return RatioTestResult(
        ratio=float(ratio),
        f_statistic=float(f_stat),
        p_value=p_upper,
        df_pre=df_pre,
        df_post=df_post,
    )


# ---------------------------------------------------------------------------
# 3. MMD two-sample test (RBF + permutation null)
# ---------------------------------------------------------------------------


def _median_pairwise_distance(values: np.ndarray) -> float:
    """Median-heuristic bandwidth: median of pairwise |x_i − x_j|."""
    n = values.size
    if n < 2:
        return 1.0
    diff = np.abs(values[:, None] - values[None, :])
    iu = np.triu_indices(n, k=1)
    pair = diff[iu]
    if pair.size == 0:
        return 1.0
    med = float(np.median(pair))
    return med if med > 0.0 else 1.0


def _rbf_kernel_matrix(a: np.ndarray, b: np.ndarray, bandwidth: float) -> np.ndarray:
    """``K[i, j] = exp(−(a_i − b_j)² / (2 · bandwidth²))`` for 1-D inputs."""
    diff = a[:, None] - b[None, :]
    return np.exp(-(diff * diff) / (2.0 * bandwidth * bandwidth))


def _mmd2(K_pp: np.ndarray, K_qq: np.ndarray, K_pq: np.ndarray) -> float:
    """Biased MMD² estimator: ``mean(K_pp) + mean(K_qq) − 2·mean(K_pq)``."""
    return float(K_pp.mean() + K_qq.mean() - 2.0 * K_pq.mean())


def conservation_mmd_test(
    r_pre: np.ndarray | Sequence[float] | float,
    r_post: np.ndarray | Sequence[float] | float,
    *,
    config: ConservationConfig | None = None,
    rng: np.random.Generator | None = None,
) -> MMDResult:
    """Two-sample MMD with RBF kernel + median-heuristic bandwidth.

    Permutation null: pool the two samples, randomly split into two halves
    of the original sizes, compute MMD² on the shuffle, repeat
    ``mmd_permutations`` times. The p-value is
    ``(1 + #{mmd² ≥ observed}) / (1 + B)`` (the standard plus-one
    correction so observed-only-tied counts as one permutation).
    """
    cfg = config or ConservationConfig()
    pre = _flatten_residual(r_pre)
    post = _flatten_residual(r_post)
    _ensure_nonempty("r_pre", pre)
    _ensure_nonempty("r_post", post)

    generator = rng if rng is not None else np.random.default_rng()

    # Subsample for tractability — kernel matrices are n × n
    n_pre, n_post = pre.size, post.size
    cap = cfg.mmd_subsample_cap
    if cap is not None and n_pre > cap:
        pre = pre[generator.choice(n_pre, size=cap, replace=False)]
    if cap is not None and n_post > cap:
        post = post[generator.choice(n_post, size=cap, replace=False)]
    n_pre_eff, n_post_eff = pre.size, post.size

    bandwidth = _median_pairwise_distance(np.concatenate([pre, post]))

    K_pp = _rbf_kernel_matrix(pre, pre, bandwidth)
    K_qq = _rbf_kernel_matrix(post, post, bandwidth)
    K_pq = _rbf_kernel_matrix(pre, post, bandwidth)
    observed = _mmd2(K_pp, K_qq, K_pq)

    # Permutation null
    pooled = np.concatenate([pre, post])
    perm_count = 0
    for _ in range(cfg.mmd_permutations):
        perm = generator.permutation(pooled)
        a = perm[:n_pre_eff]
        b = perm[n_pre_eff:]
        K_aa = _rbf_kernel_matrix(a, a, bandwidth)
        K_bb = _rbf_kernel_matrix(b, b, bandwidth)
        K_ab = _rbf_kernel_matrix(a, b, bandwidth)
        if _mmd2(K_aa, K_bb, K_ab) >= observed:
            perm_count += 1

    p_value = (1 + perm_count) / (1 + cfg.mmd_permutations)
    return MMDResult(
        mmd2=float(observed),
        p_value=float(p_value),
        bandwidth=float(bandwidth),
        n_permutations=int(cfg.mmd_permutations),
        subsample_size=int(min(n_pre_eff, n_post_eff)),
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def conservation_significance(
    r_pre: np.ndarray | Sequence[float] | float,
    r_post: np.ndarray | Sequence[float] | float,
    *,
    config: ConservationConfig | None = None,
    rng: np.random.Generator | None = None,
) -> ConservationSignificance:
    """Run all three tests on a single ``(r_pre, r_post)`` pair.

    The bootstrap CI runs on ``r_post`` only (the post-projection
    residual is what we care about); the ratio and MMD tests compare the
    two distributions.
    """
    cfg = config or ConservationConfig()
    return ConservationSignificance(
        residual_ci_post=conservation_residual_ci(r_post, config=cfg, rng=rng),
        ratio_test=conservation_ratio_test(r_pre, r_post),
        mmd_test=conservation_mmd_test(r_pre, r_post, config=cfg, rng=rng),
    )
