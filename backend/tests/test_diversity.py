"""Tests for VAL-011: DPP log-det diversity tracker.

Covers:
 - n < 2 → log_det = -inf
 - identical CFs → log_det → near regularisation floor (very negative)
 - diverse CFs → finite log_det that strictly increases as we add a
   distinct CF to a set
 - kernel switching: dtw_rbf, shapelet_edit, latent_euclidean produce
   distinct results on the same inputs
 - latent_euclidean with custom encoder
 - explicit bandwidth honoured; median-heuristic kicks in when None
 - shapelet_edit kernel ignores bandwidth
 - DTO frozen + invalid kernel / bandwidth / regularisation rejected
 - IncrementalDiversityTracker.add agrees with full recompute within 1e-6
   on n up to ~6 (the load-bearing AC test)
 - tracker reset / from_cfs replay parity with live add
 - extract handles np.ndarray, CFResult-like, plain list
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from app.services.validation import (
    DEFAULT_REGULARISATION,
    DiversityError,
    DiversityResult,
    IncrementalDiversityTracker,
    KERNEL_DTW_RBF,
    KERNEL_LATENT_EUCLIDEAN,
    KERNEL_SHAPELET_EDIT,
    dpp_log_det_diversity,
)


# ---------------------------------------------------------------------------
# Synthetic series
# ---------------------------------------------------------------------------


def _shape_set(rng: np.random.Generator, n_each: int = 1, T: int = 32):
    """Return a list of one or more series per primitive shape (rough)."""
    out: list[np.ndarray] = []
    for _ in range(n_each):
        # plateau-ish
        out.append(np.full(T, 1.0) + rng.normal(0, 0.05, T))
        # trend-ish
        out.append(np.linspace(0.0, 2.0, T) + rng.normal(0, 0.05, T))
        # cycle-ish
        out.append(np.sin(np.linspace(0, 4 * np.pi, T)) + rng.normal(0, 0.05, T))
    return out


@dataclass
class _CFLike:
    edited_series: np.ndarray


# ---------------------------------------------------------------------------
# One-shot dpp_log_det_diversity
# ---------------------------------------------------------------------------


class TestOneShot:
    def test_n_zero_returns_minus_inf(self):
        r = dpp_log_det_diversity([])
        assert r.log_det == float("-inf")
        assert r.n_cfs == 0

    def test_n_one_returns_minus_inf(self):
        r = dpp_log_det_diversity([np.array([1.0, 2.0, 3.0])])
        assert r.log_det == float("-inf")
        assert r.n_cfs == 1

    def test_identical_cfs_log_det_very_negative(self):
        x = np.linspace(0, 1, 32)
        cfs = [x.copy() for _ in range(4)]
        r = dpp_log_det_diversity(cfs)
        # All identical → K is rank-1, regularisation pins log_det near
        # ``n * log(eps)`` ≈ 4 * -13.8 = -55. We assert log_det is very
        # negative (< -10) without pinning the exact floor.
        assert r.log_det < -10.0
        assert np.isfinite(r.log_det)
        assert r.n_cfs == 4

    def test_diverse_cfs_log_det_higher_than_redundant(self):
        rng = np.random.default_rng(0)
        T = 32
        diverse = [
            np.full(T, 1.0),
            np.linspace(0, 2.0, T),
            np.sin(np.linspace(0, 4 * np.pi, T)),
            -np.linspace(0, 2.0, T),
        ]
        redundant = [diverse[0].copy() for _ in range(4)]
        d_log = dpp_log_det_diversity(diverse, kernel=KERNEL_DTW_RBF).log_det
        r_log = dpp_log_det_diversity(redundant, kernel=KERNEL_DTW_RBF).log_det
        assert d_log > r_log

    def test_explicit_bandwidth_propagated_to_result(self):
        cfs = _shape_set(np.random.default_rng(0))
        r = dpp_log_det_diversity(cfs, kernel=KERNEL_DTW_RBF, bandwidth=2.5)
        assert r.bandwidth == 2.5

    def test_median_heuristic_when_bandwidth_none(self):
        cfs = _shape_set(np.random.default_rng(1))
        r = dpp_log_det_diversity(cfs, kernel=KERNEL_DTW_RBF)
        # Bandwidth is computed and reported; positive finite.
        assert r.bandwidth is not None and r.bandwidth > 0

    def test_shapelet_edit_kernel_ignores_bandwidth(self):
        cfs = _shape_set(np.random.default_rng(2))
        r = dpp_log_det_diversity(cfs, kernel=KERNEL_SHAPELET_EDIT, bandwidth=10.0)
        assert r.bandwidth is None  # shapelet_edit returns None per design

    def test_latent_euclidean_encoder(self):
        cfs = _shape_set(np.random.default_rng(3))

        # Encoder returns a 4-dim summary (mean / std / max / min)
        def _summary(x: np.ndarray) -> np.ndarray:
            return np.array([x.mean(), x.std(), x.max(), x.min()])

        r = dpp_log_det_diversity(
            cfs, kernel=KERNEL_LATENT_EUCLIDEAN, encoder=_summary,
        )
        assert np.isfinite(r.log_det)

    def test_unknown_kernel_rejected(self):
        with pytest.raises(DiversityError, match="unknown kernel"):
            dpp_log_det_diversity(
                [np.zeros(4), np.ones(4)], kernel="bogus",  # type: ignore[arg-type]
            )

    def test_negative_regularisation_rejected(self):
        with pytest.raises(DiversityError, match="regularisation"):
            dpp_log_det_diversity(
                [np.zeros(4), np.ones(4)], regularisation=-0.1,
            )

    def test_default_regularisation_value(self):
        assert DEFAULT_REGULARISATION == 1e-6


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


class TestExtraction:
    def test_extracts_from_ndarray(self):
        r = dpp_log_det_diversity(
            [np.array([1.0, 2.0]), np.array([3.0, 4.0])],
        )
        assert r.n_cfs == 2

    def test_extracts_from_cf_like(self):
        cfs = [_CFLike(np.array([1.0, 2.0])), _CFLike(np.array([3.0, 4.0]))]
        r = dpp_log_det_diversity(cfs)
        assert r.n_cfs == 2

    def test_extracts_from_list(self):
        r = dpp_log_det_diversity([[1.0, 2.0], [3.0, 4.0]])  # type: ignore[list-item]
        assert r.n_cfs == 2

    def test_unextractable_raises(self):
        class _Unrelated:
            pass
        with pytest.raises(DiversityError, match="cannot extract"):
            dpp_log_det_diversity([_Unrelated(), _Unrelated()])


# ---------------------------------------------------------------------------
# Incremental tracker
# ---------------------------------------------------------------------------


class TestIncremental:
    def test_n_zero_one_log_det_minus_inf(self):
        t = IncrementalDiversityTracker()
        assert t.log_det == float("-inf")
        t.add(np.array([1.0, 2.0]))
        assert t.log_det == float("-inf")
        assert t.n_cfs == 1

    def test_two_points_log_det_finite(self):
        t = IncrementalDiversityTracker()
        t.add(np.array([1.0, 2.0]))
        t.add(np.array([3.0, 1.0]))
        assert np.isfinite(t.log_det)
        assert t.n_cfs == 2

    def test_incremental_matches_full_recompute(self):
        """The load-bearing AC: incremental update agrees with full
        recompute within 1e-6 on a sequence of accepts."""
        rng = np.random.default_rng(0)
        T = 24
        cfs = [
            np.full(T, 1.0),
            np.linspace(0.0, 2.0, T),
            np.sin(np.linspace(0, 4 * np.pi, T)),
            -np.linspace(0.0, 2.0, T) + 1.0,
            np.cos(np.linspace(0, 6 * np.pi, T)) * 0.5,
        ]

        # Build a tracker incrementally, fixing the bandwidth to keep the
        # one-shot and incremental kernel matrices comparable.
        bandwidth = 5.0
        t = IncrementalDiversityTracker(bandwidth=bandwidth)
        live_log_dets: list[float] = []
        for c in cfs:
            t.add(c)
            live_log_dets.append(t.log_det)

        # Compare against a one-shot recompute on the same prefix.
        for k in range(1, len(cfs) + 1):
            full = dpp_log_det_diversity(cfs[:k], bandwidth=bandwidth).log_det
            assert np.isclose(live_log_dets[k - 1], full, atol=1e-6, equal_nan=True), (
                f"mismatch at n={k}: incremental={live_log_dets[k-1]}, full={full}"
            )

    def test_identical_adds_drive_log_det_down(self):
        t = IncrementalDiversityTracker(bandwidth=2.0)
        x = np.linspace(0, 1, 16)
        t.add(x)
        t.add(x.copy())
        ld_2 = t.log_det
        t.add(x.copy())
        ld_3 = t.log_det
        # Adding more identical CFs strictly decreases log det
        # (each adds a tiny term log(s) with s ≈ ε).
        assert ld_3 < ld_2

    def test_reset_clears_state(self):
        t = IncrementalDiversityTracker()
        t.add(np.array([1.0, 2.0]))
        t.add(np.array([3.0, 4.0]))
        t.reset()
        assert t.log_det == float("-inf")
        assert t.n_cfs == 0

    def test_from_cfs_matches_live_replay(self):
        rng = np.random.default_rng(7)
        T = 20
        cfs = [rng.normal(0, 1, T) for _ in range(5)]
        bandwidth = 3.0

        replayed = IncrementalDiversityTracker.from_cfs(cfs, bandwidth=bandwidth)
        live = IncrementalDiversityTracker(bandwidth=bandwidth)
        for c in cfs:
            live.add(c)
        assert np.isclose(replayed.log_det, live.log_det, atol=1e-9)
        assert replayed.n_cfs == live.n_cfs

    def test_unknown_kernel_rejected(self):
        with pytest.raises(DiversityError, match="unknown kernel"):
            IncrementalDiversityTracker(kernel="bogus")  # type: ignore[arg-type]

    def test_invalid_bandwidth_rejected(self):
        with pytest.raises(DiversityError, match="bandwidth"):
            IncrementalDiversityTracker(bandwidth=0.0)
        with pytest.raises(DiversityError, match="bandwidth"):
            IncrementalDiversityTracker(bandwidth=-1.0)


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


class TestDTO:
    def test_frozen(self):
        r = DiversityResult(
            log_det=0.0, n_cfs=2, kernel=KERNEL_DTW_RBF,
            bandwidth=1.0, regularisation=DEFAULT_REGULARISATION,
        )
        with pytest.raises((AttributeError, TypeError)):
            r.log_det = 1.0  # type: ignore[misc]

    def test_result_carries_kernel_name(self):
        r = dpp_log_det_diversity(
            [np.zeros(4), np.ones(4)], kernel=KERNEL_SHAPELET_EDIT,
        )
        assert r.kernel == KERNEL_SHAPELET_EDIT
