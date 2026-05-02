"""Tests for VAL-013: Cherry-picking risk detector.

Covers:
 - n_accepted < min_accepted → trivial result (score=0, p=1)
 - uniform random selection → low score (KS does not reject)
 - deliberately top-quantile selection → score → 1
 - deliberately bottom-quantile selection → score → 1, low quantile mean
 - distribution cache: sampler called once per instance_key, multiple
   accepts on same key don't re-sample
 - default_utility_fn weighting
 - default_utility_fn warns on weights that don't sum to 1
 - default_utility_fn handles missing attributes
 - utility_fn returning non-finite raises CherryPickingError
 - empty sampler raises CherryPickingError
 - reset clears state and cache
 - replay constructor parity
 - DTO frozen + threshold validation
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pytest

from app.services.validation import (
    AdmissibleCFSampler,
    CherryPickingDetector,
    CherryPickingError,
    CherryPickingScore,
    DEFAULT_TIP_SCORE_THRESHOLD,
    DEFAULT_UTILITY_WEIGHTS,
    UtilityFn,
    default_utility_fn,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


@dataclass
class _CFStub:
    """Tiny CF-like with the three default-utility attributes."""

    plausibility: float = 0.5
    sparsity: float = 0.5
    is_valid: float = 1.0


class _ListSampler:
    """Sampler that returns a fixed list of CF-like draws and records call count."""

    def __init__(self, draws: list[_CFStub]) -> None:
        self.draws = list(draws)
        self.calls = 0
        self.last_n: int | None = None
        self.last_x: object = None

    def sample(self, x_original: object, n: int) -> list[_CFStub]:
        self.calls += 1
        self.last_n = n
        self.last_x = x_original
        return list(self.draws)


def _stubs_for_quantiles(quantile_targets: list[float], dist_size: int = 100) -> list[_CFStub]:
    """Build a list of accepted-CF stubs whose utility is the q-th value of
    a linear utility distribution, so the empirical quantile equals q.

    Distribution: sorted ``np.linspace(0, 1, dist_size)``. A CF-stub with
    plausibility = ``q``-th value will produce empirical-CDF rank = q.
    """
    return [_CFStub(plausibility=q, sparsity=0.0, is_valid=0.0) for q in quantile_targets]


def _uniform_distribution_sampler(dist_size: int = 100) -> _ListSampler:
    """Sampler returning ``dist_size`` CF stubs with utilities evenly
    spaced in [0, 1] under default weights."""
    # default_utility_fn = 0.4·plaus + 0.3·sparsity + 0.3·valid
    # Setting sparsity=0 and is_valid=0 makes utility = 0.4·plaus.
    # We want the *quantile* lookup to span [0, 1], so use raw utilities
    # we know exactly: choose plaus values so utilities = linspace(0, 0.4, n).
    plaus_vals = np.linspace(0.0, 1.0, dist_size)
    return _ListSampler([
        _CFStub(plausibility=float(p), sparsity=0.0, is_valid=0.0)
        for p in plaus_vals
    ])


# ---------------------------------------------------------------------------
# default_utility_fn
# ---------------------------------------------------------------------------


class TestDefaultUtility:
    def test_weighted_sum(self):
        cf = _CFStub(plausibility=1.0, sparsity=1.0, is_valid=1.0)
        assert default_utility_fn(cf) == pytest.approx(1.0)

    def test_zero_inputs(self):
        cf = _CFStub(plausibility=0.0, sparsity=0.0, is_valid=0.0)
        assert default_utility_fn(cf) == 0.0

    def test_default_weights_match_ac(self):
        assert DEFAULT_UTILITY_WEIGHTS == (0.4, 0.3, 0.3)

    def test_partial_weighted(self):
        cf = _CFStub(plausibility=1.0, sparsity=0.0, is_valid=0.0)
        # 0.4 * 1 + 0.3 * 0 + 0.3 * 0 = 0.4
        assert default_utility_fn(cf) == pytest.approx(0.4)

    def test_clip_to_unit_interval(self):
        cf = _CFStub(plausibility=2.0, sparsity=2.0, is_valid=2.0)
        # All clipped to 1.0 → weights sum to 1.0 → 1.0
        assert default_utility_fn(cf) == pytest.approx(1.0)

    def test_negative_clipped_to_zero(self):
        cf = _CFStub(plausibility=-0.5, sparsity=-0.5, is_valid=-0.5)
        assert default_utility_fn(cf) == 0.0

    def test_missing_attributes_default_to_zero(self):
        class _Empty:
            pass
        u = default_utility_fn(_Empty())
        assert u == 0.0

    def test_warns_on_weights_not_summing_to_one(self):
        cf = _CFStub()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            default_utility_fn(cf, weights=(0.5, 0.5, 0.5))
        assert any("weights" in str(w.message) for w in caught)


# ---------------------------------------------------------------------------
# Detector — small-n trivial result
# ---------------------------------------------------------------------------


class TestSmallN:
    def test_under_min_accepted_returns_trivial(self):
        sampler = _uniform_distribution_sampler()
        det = CherryPickingDetector(sampler, min_accepted=3)
        det.on_accepted(_CFStub(plausibility=0.5), x_original="x1", instance_key="x1")
        det.on_accepted(_CFStub(plausibility=0.5), x_original="x1", instance_key="x1")
        r = det.score()
        assert r.score == 0.0
        assert r.p_value == 1.0
        assert r.recommendation is None
        assert r.n_accepted == 2
        assert r.tip_should_fire is False

    def test_zero_accepts(self):
        sampler = _uniform_distribution_sampler()
        det = CherryPickingDetector(sampler)
        r = det.score()
        assert r.n_accepted == 0
        assert r.score == 0.0
        assert r.p_value == 1.0


# ---------------------------------------------------------------------------
# Detector — uniform vs cherry-picked
# ---------------------------------------------------------------------------


class TestKSCalibration:
    def test_uniform_random_quantiles_low_score(self):
        """Sample accepted-CFs whose utilities are drawn uniformly from
        the admissible distribution → KS does not reject."""
        rng = np.random.default_rng(42)
        sampler = _uniform_distribution_sampler(dist_size=200)
        det = CherryPickingDetector(sampler, min_accepted=3)
        # Draw 30 accepted utilities uniformly from [0, 0.4] (the
        # admissible utility range for sparsity=0 / is_valid=0 stubs).
        for _ in range(30):
            target_p = float(rng.uniform(0, 1))
            det.on_accepted(
                _CFStub(plausibility=target_p, sparsity=0.0, is_valid=0.0),
                x_original="x1", instance_key="x1",
            )
        r = det.score()
        # Uniform draws → high KS p-value → low score
        assert r.score < 0.7
        assert abs(r.accepted_quantile_mean - 0.5) < 0.15

    def test_top_quantile_cherry_picking_high_score(self):
        sampler = _uniform_distribution_sampler(dist_size=200)
        det = CherryPickingDetector(sampler, min_accepted=3)
        # Always pick the top of the utility distribution
        for _ in range(20):
            det.on_accepted(
                _CFStub(plausibility=1.0, sparsity=0.0, is_valid=0.0),
                x_original="x1", instance_key="x1",
            )
        r = det.score()
        assert r.score > 0.95
        assert r.accepted_quantile_mean > 0.9
        assert r.tip_should_fire is True
        assert r.recommendation is not None
        assert "top utility" in r.recommendation.lower()

    def test_bottom_quantile_cherry_picking_high_score(self):
        sampler = _uniform_distribution_sampler(dist_size=200)
        det = CherryPickingDetector(sampler, min_accepted=3)
        for _ in range(20):
            det.on_accepted(
                _CFStub(plausibility=0.0, sparsity=0.0, is_valid=0.0),
                x_original="x1", instance_key="x1",
            )
        r = det.score()
        assert r.score > 0.95
        assert r.accepted_quantile_mean < 0.1
        assert r.tip_should_fire is True
        assert r.recommendation is not None
        assert "bottom" in r.recommendation.lower()

    def test_middle_concentrated_triggers_generic_recommendation(self):
        sampler = _uniform_distribution_sampler(dist_size=200)
        det = CherryPickingDetector(sampler, min_accepted=3)
        # All accepted CFs at middle utility — non-uniform but neither
        # extreme top nor extreme bottom
        for _ in range(20):
            det.on_accepted(
                _CFStub(plausibility=0.5, sparsity=0.0, is_valid=0.0),
                x_original="x1", instance_key="x1",
            )
        r = det.score()
        assert r.score > 0.9
        assert r.recommendation is not None


# ---------------------------------------------------------------------------
# Distribution caching
# ---------------------------------------------------------------------------


class TestDistributionCache:
    def test_sampler_called_once_per_key(self):
        sampler = _uniform_distribution_sampler()
        det = CherryPickingDetector(sampler)
        for _ in range(5):
            det.on_accepted(_CFStub(), x_original="x1", instance_key="x1")
        assert sampler.calls == 1

    def test_separate_keys_separate_calls(self):
        sampler = _uniform_distribution_sampler()
        det = CherryPickingDetector(sampler)
        det.on_accepted(_CFStub(), x_original="x1", instance_key="x1")
        det.on_accepted(_CFStub(), x_original="x2", instance_key="x2")
        det.on_accepted(_CFStub(), x_original="x1", instance_key="x1")
        assert sampler.calls == 2

    def test_sample_size_propagated(self):
        sampler = _uniform_distribution_sampler()
        det = CherryPickingDetector(sampler, sample_size=137)
        det.on_accepted(_CFStub(), x_original="x1", instance_key="x1")
        assert sampler.last_n == 137

    def test_default_instance_key_uses_id(self):
        sampler = _uniform_distribution_sampler()
        det = CherryPickingDetector(sampler)
        x = object()
        det.on_accepted(_CFStub(), x_original=x)
        # Cached under id(x)
        assert id(x) in det.cached_instance_keys

    def test_quantile_returned_from_on_accepted(self):
        sampler = _uniform_distribution_sampler()
        det = CherryPickingDetector(sampler)
        # Accepted utility = 1.0 → top of distribution → quantile = 1.0
        q = det.on_accepted(
            _CFStub(plausibility=1.0, sparsity=0.0, is_valid=0.0),
            x_original="x1", instance_key="x1",
        )
        assert q == 1.0


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrors:
    def test_sampler_returns_empty_raises(self):
        det = CherryPickingDetector(_ListSampler([]))
        with pytest.raises(CherryPickingError, match="no admissible"):
            det.on_accepted(_CFStub(), x_original="x1", instance_key="x1")

    def test_non_finite_accepted_utility_raises(self):
        sampler = _uniform_distribution_sampler()

        def _bad_util(cf: object) -> float:
            return float("nan")
        det = CherryPickingDetector(sampler, utility_fn=_bad_util)
        with pytest.raises(CherryPickingError, match="non-finite"):
            det.on_accepted(_CFStub(), x_original="x1", instance_key="x1")

    def test_invalid_sample_size_rejected(self):
        with pytest.raises(ValueError, match="sample_size"):
            CherryPickingDetector(_uniform_distribution_sampler(), sample_size=0)

    def test_invalid_min_accepted_rejected(self):
        with pytest.raises(ValueError, match="min_accepted"):
            CherryPickingDetector(_uniform_distribution_sampler(), min_accepted=0)

    def test_invalid_threshold_rejected(self):
        with pytest.raises(ValueError, match="tip_score_threshold"):
            CherryPickingDetector(
                _uniform_distribution_sampler(), tip_score_threshold=1.5,
            )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_reset_clears_quantiles_and_cache(self):
        sampler = _uniform_distribution_sampler()
        det = CherryPickingDetector(sampler)
        det.on_accepted(_CFStub(), x_original="x1", instance_key="x1")
        det.on_accepted(_CFStub(), x_original="x2", instance_key="x2")
        det.reset()
        assert det.n_accepted == 0
        assert det.cached_instance_keys == []

    def test_replay_matches_live(self):
        sampler_a = _uniform_distribution_sampler()
        sampler_b = _uniform_distribution_sampler()
        history = [
            (_CFStub(plausibility=0.9), "x1", "x1"),
            (_CFStub(plausibility=0.1), "x1", "x1"),
            (_CFStub(plausibility=0.5), "x2", "x2"),
        ]
        live = CherryPickingDetector(sampler_a)
        for cf, x, k in history:
            live.on_accepted(cf, x_original=x, instance_key=k)
        replayed = CherryPickingDetector(sampler_b)
        replayed.replay(history)
        assert replayed.n_accepted == live.n_accepted
        assert replayed.accepted_quantiles == live.accepted_quantiles


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


class TestDTO:
    def test_frozen(self):
        s = CherryPickingScore(
            score=0.0, accepted_quantile_mean=0.5, expected_under_random=0.5,
            p_value=1.0, recommendation=None, n_accepted=0, tip_should_fire=False,
        )
        with pytest.raises((AttributeError, TypeError)):
            s.score = 1.0  # type: ignore[misc]

    def test_default_threshold_value(self):
        assert DEFAULT_TIP_SCORE_THRESHOLD == 0.7
