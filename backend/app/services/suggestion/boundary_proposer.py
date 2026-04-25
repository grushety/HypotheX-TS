"""Boundary proposer with ClaSP / PELT / BOCPD backends (SEG-009).

Produces candidate boundary timestamps from a time series using an
unsupervised change-point detector.  Method is configurable:

  clasp  – profile-based binary segmentation (Schäfer et al. 2021, CIKM).
           Tries the `claspy` library; falls back to a numpy implementation
           that uses k-NN cross-classification over globally-normalised
           sliding windows.  Global (not per-window) normalisation is used
           so that piecewise-constant signals remain discriminable.
  pelt   – PELT optimal segmentation via `ruptures` (Killick et al. 2012).
  bocpd  – Bayesian Online Changepoint Detection (Adams & MacKay 2007)
           with Normal-Inverse-Gamma conjugate prior.

Paper references:
- Schäfer, Ermshaus, Leser (2021) "ClaSP — Time Series Segmentation",
  CIKM 2021.
- Killick, Fearnhead, Eckley (2012) "Optimal Detection of Changepoints
  With a Linear Computational Cost", JASA 107(500):1590–1598.
- Adams & MacKay (2007) "Bayesian Online Changepoint Detection",
  arXiv:0710.3742.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Literal, Sequence

import numpy as np
from scipy.special import gammaln  # noqa: PLC0415

logger = logging.getLogger(__name__)

_METHODS: tuple[str, ...] = ("clasp", "pelt", "bocpd")


# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BoundaryCandidate:
    """A single detected change-point candidate.

    Attributes:
        timestamp: Index in the original series where the boundary falls.
        score:     Detection confidence in [0, 1] (higher = more certain).
        method:    Algorithm that produced this candidate.
    """

    timestamp: int
    score: float
    method: str


@dataclass(frozen=True)
class BoundaryProposerConfig:
    """Configuration for BoundaryProposer.

    Attributes:
        method:                 Default detection algorithm.
        min_segment_length:     No candidate may produce a segment shorter
                                than this many samples.
        max_cps:                Hard limit on returned candidates (None = no limit).
        pelt_penalty:           PELT regularisation penalty λ.  Exposed so
                                callers can tune sensitivity.  Ref: Killick
                                et al. (2012) eq. (3).
        pelt_model:             Ruptures cost model ('rbf', 'l2', 'l1', etc.).
        bocpd_mean_run_length:  Expected duration of a run (1/hazard rate).
                                Ref: Adams & MacKay (2007) eq. (8).
        bocpd_threshold:        Minimum P(changepoint) to emit a candidate.
        clasp_window_len:       Sliding window length L. None = auto-select.
        clasp_k_neighbors:      k for k-NN cross-classification in ClaSP profile.
    """

    method: Literal["clasp", "pelt", "bocpd"] = "clasp"
    min_segment_length: int = 10
    max_cps: int | None = None
    pelt_penalty: float = 1.0
    pelt_model: str = "rbf"
    bocpd_mean_run_length: float = 50.0
    bocpd_threshold: float = 0.4
    clasp_window_len: int | None = None
    clasp_k_neighbors: int = 3


# ---------------------------------------------------------------------------
# BoundaryProposer
# ---------------------------------------------------------------------------


class BoundaryProposer:
    """Change-point based boundary proposer.

    Usage::

        proposer = BoundaryProposer()
        candidates = proposer.propose(X, method='clasp', max_cps=8)
    """

    def __init__(self, config: BoundaryProposerConfig | None = None) -> None:
        self._config = config or BoundaryProposerConfig()

    def propose(
        self,
        X: np.ndarray | list[float] | list[list[float]],
        method: Literal["clasp", "pelt", "bocpd"] | None = None,
        max_cps: int | None = None,
    ) -> list[BoundaryCandidate]:
        """Detect change points and return sorted boundary candidates.

        Args:
            X:       1-D or 2-D time series.  Channels are averaged if 2-D.
            method:  Override the config method.
            max_cps: Max candidates (None → config.max_cps, unbounded if both None).

        Returns:
            List of BoundaryCandidate sorted by timestamp ascending.

        Raises:
            ValueError: Unknown method string.
        """
        arr = _normalise_input(X)
        if len(arr) < 2:
            return []

        m = method or self._config.method
        if m not in _METHODS:
            raise ValueError(
                f"Unknown boundary detection method: {m!r}. Choose from {_METHODS}."
            )

        max_k = max_cps if max_cps is not None else self._config.max_cps
        min_seg = self._config.min_segment_length

        if m == "clasp":
            candidates = self._propose_clasp(arr, max_k, min_seg)
        elif m == "pelt":
            candidates = self._propose_pelt(arr, max_k, min_seg)
        else:
            candidates = self._propose_bocpd(arr, max_k, min_seg)

        return sorted(candidates, key=lambda c: c.timestamp)

    # ------------------------------------------------------------------
    # ClaSP backend
    # ------------------------------------------------------------------

    def _propose_clasp(
        self, arr: np.ndarray, max_cps: int | None, min_seg_len: int
    ) -> list[BoundaryCandidate]:
        """ClaSP binary segmentation (Schäfer et al. 2021, CIKM).

        Tries the `claspy` library; falls back to numpy if unavailable.
        """
        try:
            return self._propose_clasp_library(arr, max_cps, min_seg_len)
        except ImportError:
            logger.debug("claspy not available; using numpy ClaSP fallback.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("claspy failed (%s); using numpy fallback.", exc)

        return self._propose_clasp_numpy(arr, max_cps, min_seg_len)

    def _propose_clasp_library(
        self, arr: np.ndarray, max_cps: int | None, min_seg_len: int
    ) -> list[BoundaryCandidate]:
        """Thin wrapper around the `claspy` library."""
        import claspy  # noqa: PLC0415

        n_segments = (max_cps + 1) if max_cps else None
        window_size = self._config.clasp_window_len
        seg = claspy.BinaryClaSPSegmentation(
            n_segments=n_segments,
            window_size=window_size,
        )
        seg.fit(arr)
        change_points = seg.predict()
        if len(change_points) == 0:
            return []

        profile = getattr(seg, "profile", None)
        candidates = []
        for cp in change_points:
            idx = int(cp)
            if idx <= min_seg_len or idx >= len(arr) - min_seg_len:
                continue
            score = float(profile[idx]) if profile is not None and idx < len(profile) else 0.5
            candidates.append(BoundaryCandidate(timestamp=idx, score=score, method="clasp"))
        return candidates

    def _propose_clasp_numpy(
        self, arr: np.ndarray, max_cps: int | None, min_seg_len: int
    ) -> list[BoundaryCandidate]:
        """NumPy ClaSP: k-NN cross-classification profile + binary segmentation.

        Uses globally-normalised windows (not per-window z-score) so that
        piecewise-constant segments at different levels are distinguishable.
        Ref: Schäfer et al. (2021) Algorithm 1 (profile + binary segmentation).
        """
        n = len(arr)
        window_len = self._config.clasp_window_len or max(5, min(50, n // 10))

        if n < 2 * window_len + min_seg_len:
            return []

        profile = _clasp_profile(arr, window_len, self._config.clasp_k_neighbors)
        change_points = _binary_segmentation(profile, max_cps or 8, min_seg_len, n)

        return [
            BoundaryCandidate(timestamp=cp, score=score, method="clasp")
            for cp, score in change_points
        ]

    # ------------------------------------------------------------------
    # PELT backend
    # ------------------------------------------------------------------

    def _propose_pelt(
        self, arr: np.ndarray, max_cps: int | None, min_seg_len: int
    ) -> list[BoundaryCandidate]:
        """PELT via ruptures (Killick et al. 2012, JASA).

        Finds the globally optimal set of change points minimising a
        penalised sum-of-costs.  Penalty λ is exposed in BoundaryProposerConfig
        and not hardcoded.  Ref: Killick et al. (2012) eq. (3).
        """
        import ruptures  # noqa: PLC0415

        n = len(arr)
        arr_2d = arr.reshape(-1, 1)

        try:
            algo = ruptures.Pelt(
                model=self._config.pelt_model,
                min_size=max(1, min_seg_len),
                jump=1,
            )
            algo.fit(arr_2d)
            cps_raw = algo.predict(pen=self._config.pelt_penalty)
        except Exception as exc:  # noqa: BLE001
            logger.warning("PELT detection failed (%s); returning empty.", exc)
            return []

        # ruptures returns end-of-segment indices; last entry = n (not a boundary)
        cps = [cp for cp in cps_raw if min_seg_len <= cp <= n - min_seg_len]
        if max_cps is not None:
            cps = cps[:max_cps]

        candidates = []
        for cp in cps:
            score = _local_shift_score(arr, cp, min_seg_len)
            candidates.append(BoundaryCandidate(timestamp=cp, score=score, method="pelt"))
        return candidates

    # ------------------------------------------------------------------
    # BOCPD backend
    # ------------------------------------------------------------------

    def _propose_bocpd(
        self, arr: np.ndarray, max_cps: int | None, min_seg_len: int
    ) -> list[BoundaryCandidate]:
        """BOCPD with Normal-Inverse-Gamma conjugate prior (Adams & MacKay 2007).

        Hazard function H(r) = 1/bocpd_mean_run_length (constant hazard).
        Ref: Adams & MacKay (2007) arXiv:0710.3742, Algorithm 1.
        Eq. (7): Student-T predictive via NIG posterior.
        Eq. (8): constant hazard parameter.
        """
        change_probs = _bocpd_change_probs(
            arr, hazard_rate=1.0 / self._config.bocpd_mean_run_length
        )

        candidates_raw = _find_local_maxima(
            change_probs, self._config.bocpd_threshold, min_seg_len, len(arr)
        )

        if max_cps is not None:
            candidates_raw.sort(key=lambda x: -x[1])
            candidates_raw = candidates_raw[:max_cps]

        return [
            BoundaryCandidate(timestamp=cp, score=score, method="bocpd")
            for cp, score in candidates_raw
        ]


# ---------------------------------------------------------------------------
# ClaSP helpers
# ---------------------------------------------------------------------------


def _clasp_profile(arr: np.ndarray, window_len: int, k: int = 3) -> np.ndarray:
    """Compute ClaSP change-score profile.

    For each candidate split t, samples k windows from the left and right
    neighbourhoods and computes the k-NN cross-classification rate.  A rate
    near 1 means the two sides are easily separated → change point.

    Uses GLOBAL normalisation instead of per-window z-score so that
    piecewise-constant signals at different levels remain distinguishable.
    Ref: Schäfer et al. (2021) CIKM, Algorithm 1 profile computation.

    Args:
        arr:        1-D globally-scaled series.
        window_len: Sliding window length L.
        k:          Number of windows sampled from each neighbourhood.

    Returns:
        Profile array of shape (n,) with scores in [0, 1].
    """
    n = len(arr)
    n_windows = n - window_len + 1

    # Global (not per-window) normalisation: preserves level information.
    g_mean = float(arr.mean())
    g_std = float(arr.std()) or 1.0
    arr_g = (arr - g_mean) / g_std

    # Extract all windows using global-normalised values
    windows = np.stack([arr_g[i : i + window_len] for i in range(n_windows)])

    profile = np.zeros(n)

    for t in range(window_len, n - window_len + 1):
        # Left neighbourhood: windows whose end index <= t-1 (i.e. index <= t-window_len)
        left_end = t - window_len
        left_start = max(0, left_end - 2 * k * window_len)
        left_idx = np.arange(left_start, left_end + 1)

        # Right neighbourhood: windows starting at t or later
        right_start = t
        right_end = min(n_windows - 1, t + 2 * k * window_len)
        right_idx = np.arange(right_start, right_end + 1)

        if len(left_idx) == 0 or len(right_idx) == 0:
            continue

        # Sample up to k from each side (evenly spaced)
        kl = min(k, len(left_idx))
        kr = min(k, len(right_idx))
        l_samp = left_idx[
            np.round(np.linspace(0, len(left_idx) - 1, kl)).astype(int)
        ]
        r_samp = right_idx[
            np.round(np.linspace(0, len(right_idx) - 1, kr)).astype(int)
        ]

        all_idx = np.concatenate([l_samp, r_samp])
        labels = np.concatenate(
            [np.zeros(kl, dtype=np.int8), np.ones(kr, dtype=np.int8)]
        )
        pool = windows[all_idx]  # (kl+kr, window_len)

        # For each window compute 1-NN excluding self; count cross-boundary matches
        cross = 0
        total = len(all_idx)
        dists_all = np.sum((pool[:, None, :] - pool[None, :, :]) ** 2, axis=-1)
        np.fill_diagonal(dists_all, np.inf)
        nn_idx = np.argmin(dists_all, axis=1)
        cross = int(np.sum(labels[nn_idx] != labels))
        profile[t] = cross / total

    return profile


def _binary_segmentation(
    profile: np.ndarray, max_cps: int, min_seg_len: int, n: int
) -> list[tuple[int, float]]:
    """Binary segmentation over a change-score profile.

    Iteratively finds the highest-scoring valid position in each open search
    interval and splits it.
    Ref: Schäfer et al. (2021) binary segmentation procedure.
    """
    change_points: list[tuple[int, float]] = []
    search_intervals: list[tuple[int, int]] = [(0, n)]

    while len(change_points) < max_cps and search_intervals:
        best_pos: int | None = None
        best_score = -1.0
        best_int: tuple[int, int] | None = None

        for start, end in search_intervals:
            lo = start + min_seg_len
            hi = end - min_seg_len
            if lo >= hi:
                continue
            local = profile[lo:hi]
            if len(local) == 0:
                continue
            idx = int(np.argmax(local))
            val = float(local[idx])
            if val > best_score:
                best_score = val
                best_pos = lo + idx
                best_int = (start, end)

        if best_pos is None or best_score <= 0.0:
            break

        change_points.append((best_pos, best_score))
        search_intervals.remove(best_int)
        search_intervals.append((best_int[0], best_pos))
        search_intervals.append((best_pos, best_int[1]))

    return sorted(change_points)


# ---------------------------------------------------------------------------
# BOCPD helpers
# ---------------------------------------------------------------------------


def _bocpd_change_probs(arr: np.ndarray, hazard_rate: float) -> np.ndarray:
    """Online Bayesian changepoint probabilities via NIG conjugate prior.

    Tracks a run-length distribution P(r_t | x_{1:t}).  At each step the
    probability mass at run-length 0 is P(changepoint at t).

    Memory is bounded by tracking at most ``max_rl`` run lengths, where
    ``max_rl = min(n, ceil(5 / hazard_rate))``.  This gives O(n * max_rl)
    total work instead of O(n^2).

    Ref: Adams & MacKay (2007) arXiv:0710.3742, Algorithm 1.
         Eq. (7): Student-T predictive via NIG posterior.
         Eq. (8): constant hazard H = hazard_rate.
    """
    n = len(arr)
    hazard_rate = float(np.clip(hazard_rate, 1e-6, 1.0 - 1e-6))
    log_H = math.log(hazard_rate)
    log_1mH = math.log(1.0 - hazard_rate)

    # NIG prior hyper-parameters (vague)
    mu0, kappa0, alpha0, beta0 = 0.0, 1.0, 1.0, 1.0

    # Max run length tracked (bound memory)
    max_rl = min(n, max(1, math.ceil(5.0 / hazard_rate)))

    # Sufficient statistics for NIG posteriors indexed by run length
    mus = np.full(max_rl + 1, mu0)
    kappas = np.full(max_rl + 1, kappa0)
    alphas = np.full(max_rl + 1, alpha0)
    betas = np.full(max_rl + 1, beta0)

    # Log-probability of run-length distribution (log-space for numerical stability)
    log_R = np.full(max_rl + 1, -np.inf)
    log_R[0] = 0.0  # P(r_0 = 0) = 1

    change_probs = np.zeros(n)

    for t in range(n):
        x = float(arr[t])

        # Active run lengths: 0 to min(t, max_rl)
        active_end = min(t, max_rl) + 1

        # Predictive log-prob for each active run length (vectorised Student-T)
        log_pred = _log_student_t_vec(
            x,
            mus[:active_end],
            kappas[:active_end],
            alphas[:active_end],
            betas[:active_end],
        )

        # --- Run-length update ---
        # Hazard: P(r_t = 0) ∝ Σ P(r_{t-1} = r) * H * pred(r)
        log_cp = _logsumexp_1d(log_R[:active_end] + log_pred) + log_H

        # Continuation: P(r_t = r+1) ∝ P(r_{t-1} = r) * (1-H) * pred(r)
        new_log_R = np.full(max_rl + 1, -np.inf)
        new_log_R[0] = log_cp
        cont_end = min(active_end, max_rl)
        new_log_R[1 : cont_end + 1] = log_R[:cont_end] + log_pred[:cont_end] + log_1mH

        # Normalise
        finite = new_log_R[np.isfinite(new_log_R)]
        if len(finite) > 0:
            log_norm = _logsumexp_1d(finite)
            new_log_R -= log_norm

        # --- Sufficient statistics update (vectorised) ---
        # New run length r corresponds to having seen x after r-1 prev observations
        new_mus = np.copy(mus)
        new_kappas = np.copy(kappas)
        new_alphas = np.copy(alphas)
        new_betas = np.copy(betas)

        k_vec = kappas[:cont_end]
        mu_vec = mus[:cont_end]
        diff = x - mu_vec
        new_mus[1 : cont_end + 1] = (k_vec * mu_vec + x) / (k_vec + 1)
        new_kappas[1 : cont_end + 1] = k_vec + 1
        new_alphas[1 : cont_end + 1] = alphas[:cont_end] + 0.5
        new_betas[1 : cont_end + 1] = betas[:cont_end] + k_vec * diff**2 / (2.0 * (k_vec + 1))

        # Reset run-length-0 to prior (changepoint restarts the model)
        new_mus[0] = mu0
        new_kappas[0] = kappa0
        new_alphas[0] = alpha0
        new_betas[0] = beta0

        log_R = new_log_R
        mus = new_mus
        kappas = new_kappas
        alphas = new_alphas
        betas = new_betas

        change_probs[t] = math.exp(log_R[0]) if math.isfinite(log_R[0]) else 0.0

    return change_probs


def _log_student_t_vec(
    x: float,
    mus: np.ndarray,
    kappas: np.ndarray,
    alphas: np.ndarray,
    betas: np.ndarray,
) -> np.ndarray:
    """Vectorised log-pdf of the Student-T predictive distribution.

    The NIG predictive marginal is:
      p(x | mu, kappa, alpha, beta) = StudentT(2*alpha; mu, beta*(kappa+1)/(alpha*kappa))

    Ref: Gelman et al. "Bayesian Data Analysis" 3rd ed., Appendix A.
    """
    nu = 2.0 * alphas
    scale_sq = betas * (kappas + 1.0) / (alphas * kappas + 1e-300)
    scale_sq = np.where(scale_sq <= 0, 1e-8, scale_sq)

    log_prob = (
        gammaln((nu + 1.0) / 2.0)
        - gammaln(nu / 2.0)
        - 0.5 * np.log(nu * math.pi * scale_sq)
        - (nu + 1.0) / 2.0 * np.log(1.0 + (x - mus) ** 2 / (nu * scale_sq + 1e-300))
    )
    return np.where(np.isfinite(log_prob), log_prob, -1e10)


def _logsumexp_1d(arr: np.ndarray) -> float:
    """Numerically stable logsumexp for a 1-D array."""
    if len(arr) == 0:
        return -math.inf
    m = float(arr.max())
    if not math.isfinite(m):
        return -math.inf
    return m + math.log(float(np.sum(np.exp(arr - m))))


def _find_local_maxima(
    probs: np.ndarray,
    threshold: float,
    min_seg_len: int,
    n: int,
) -> list[tuple[int, float]]:
    """Find non-maximum-suppressed peaks in a probability array.

    Returns (timestamp, score) pairs for each local maximum above threshold,
    with at least min_seg_len spacing between adjacent peaks.
    """
    candidates: list[tuple[int, float]] = []
    half = max(1, min_seg_len // 2)
    for t in range(min_seg_len, n - min_seg_len):
        if probs[t] < threshold:
            continue
        lo = max(0, t - half)
        hi = min(n, t + half + 1)
        if float(probs[t]) >= float(probs[lo:hi].max()):
            candidates.append((t, float(probs[t])))
    return candidates


# ---------------------------------------------------------------------------
# PELT score helper
# ---------------------------------------------------------------------------


def _local_shift_score(arr: np.ndarray, t: int, window: int) -> float:
    """Estimate change magnitude at t as normalised mean-shift."""
    left = arr[max(0, t - window) : t]
    right = arr[t : min(len(arr), t + window)]
    if len(left) == 0 or len(right) == 0:
        return 0.0
    std = float(np.std(arr)) or 1.0
    shift = abs(float(np.mean(right)) - float(np.mean(left)))
    return min(1.0, shift / (std + 1e-8))


# ---------------------------------------------------------------------------
# Input normalisation
# ---------------------------------------------------------------------------


def _normalise_input(X: np.ndarray | list[float] | list[list[float]]) -> np.ndarray:
    """Convert 1-D or 2-D input to a 1-D float64 array (average channels if 2-D)."""
    arr = np.asarray(X, dtype=np.float64)
    if arr.ndim == 2:
        if arr.shape[0] > arr.shape[1]:
            arr = arr.T
        arr = arr.mean(axis=0)
    return arr.ravel()
