"""Tests for Tier-2 spike ops: remove, clip_cap, amplify, smear_to_transient,
duplicate, shift_time (OP-023).
"""

import numpy as np
import pytest

from app.services.operations.tier2.spike import (
    amplify,
    clip_cap,
    duplicate,
    remove,
    shift_time,
    smear_to_transient,
)
from app.services.operations.tier2.plateau import Tier2OpResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

N = 40
T_SPIKE = 20
SPIKE_HEIGHT = 8.0
NOISE_SIGMA = 0.1


def _spike_signal(
    n: int = N,
    t_spike: int = T_SPIKE,
    height: float = SPIKE_HEIGHT,
    noise_sigma: float = NOISE_SIGMA,
    seed: int = 42,
) -> np.ndarray:
    """Noisy plateau with one positive spike at t_spike."""
    rng = np.random.default_rng(seed)
    X = rng.normal(0.0, noise_sigma, n)
    X[t_spike] += height
    return X


def _plateau_signal(n: int = N, level: float = 2.0, noise_sigma: float = 0.05, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return level + rng.normal(0.0, noise_sigma, n)


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------


class TestRemove:
    def test_hampel_reduces_spike(self):
        X = _spike_signal()
        result = remove(X, method="hampel")
        assert result.values[T_SPIKE] < SPIKE_HEIGHT / 2

    def test_hampel_preserves_plateau_approx(self):
        X = _spike_signal()
        result = remove(X, method="hampel")
        non_spike = list(range(0, T_SPIKE - 3)) + list(range(T_SPIKE + 4, N))
        np.testing.assert_allclose(
            result.values[non_spike], X[non_spike], atol=NOISE_SIGMA * 3
        )

    def test_chen_sg_reduces_spike(self):
        X = _spike_signal()
        result = remove(X, method="chen_sg")
        assert result.values[T_SPIKE] < SPIKE_HEIGHT / 2

    def test_relabel_reclassify(self):
        result = remove(_spike_signal())
        assert result.relabel.rule_class == "RECLASSIFY_VIA_SEGMENTER"
        assert result.relabel.needs_resegment is True

    def test_op_name(self):
        assert remove(_spike_signal()).op_name == "remove"

    def test_tier(self):
        assert remove(_spike_signal()).tier == 2

    def test_caller_signal_not_mutated(self):
        X = _spike_signal()
        original_spike = X[T_SPIKE]
        remove(X)
        assert X[T_SPIKE] == original_spike

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError, match="unknown method"):
            remove(_spike_signal(), method="median_filter")

    def test_pre_shape_forwarded(self):
        result = remove(_spike_signal(), pre_shape="noise")
        assert result.relabel.new_shape == "noise"

    def test_hampel_and_chen_sg_both_reduce_large_spike(self):
        X = _spike_signal(height=20.0)
        r_h = remove(X, method="hampel")
        r_c = remove(X, method="chen_sg")
        assert r_h.values[T_SPIKE] < 10.0
        assert r_c.values[T_SPIKE] < 10.0

    def test_plateau_signal_unchanged_by_hampel(self):
        """On a clean plateau with no spikes, Hampel filter is an identity."""
        X = _plateau_signal(noise_sigma=0.0)
        result = remove(X, method="hampel")
        np.testing.assert_allclose(result.values, X, atol=1e-10)


# ---------------------------------------------------------------------------
# clip_cap
# ---------------------------------------------------------------------------


class TestClipCap:
    def test_all_values_at_or_below_cap(self):
        X = _spike_signal()
        quantile = 0.95
        cap = float(np.quantile(X, quantile))
        result = clip_cap(X, quantile=quantile)
        assert np.all(result.values <= cap + 1e-12)

    def test_below_cap_values_unchanged(self):
        X = _spike_signal()
        quantile = 0.95
        cap = float(np.quantile(X, quantile))
        result = clip_cap(X, quantile=quantile)
        mask = X < cap
        np.testing.assert_array_equal(result.values[mask], X[mask])

    def test_clipping_is_not_zeroing(self):
        """Values above cap must be replaced by cap, not by 0."""
        X = _spike_signal()
        result = clip_cap(X, quantile=0.95)
        cap = float(np.quantile(X, 0.95))
        above = X > cap
        np.testing.assert_allclose(result.values[above], cap, atol=1e-12)

    def test_relabel_preserved(self):
        result = clip_cap(_spike_signal())
        assert result.relabel.rule_class == "PRESERVED"
        assert result.relabel.new_shape == "spike"
        assert result.relabel.needs_resegment is False

    def test_op_name(self):
        assert clip_cap(_spike_signal()).op_name == "clip_cap"

    def test_tier(self):
        assert clip_cap(_spike_signal()).tier == 2

    def test_quantile_zero_raises(self):
        with pytest.raises(ValueError, match="quantile"):
            clip_cap(_spike_signal(), quantile=0.0)

    def test_quantile_negative_raises(self):
        with pytest.raises(ValueError):
            clip_cap(_spike_signal(), quantile=-0.1)

    def test_quantile_one_clips_at_max(self):
        X = _spike_signal()
        result = clip_cap(X, quantile=1.0)
        np.testing.assert_array_equal(result.values, X)

    def test_pre_shape_forwarded(self):
        result = clip_cap(_spike_signal(), pre_shape="noise")
        assert result.relabel.new_shape == "noise"


# ---------------------------------------------------------------------------
# amplify
# ---------------------------------------------------------------------------


class TestAmplify:
    def test_peak_scaled_exactly_by_alpha(self):
        X = _spike_signal(noise_sigma=0.0)
        alpha = 3.0
        result = amplify(X, t_peak=T_SPIKE, alpha=alpha, widening_sigma=0.5)
        np.testing.assert_allclose(result.values[T_SPIKE], alpha * X[T_SPIKE], atol=1e-12)

    def test_far_from_peak_near_identity(self):
        """Samples far from t_peak should be nearly unchanged (Gaussian taper)."""
        X = _spike_signal(noise_sigma=0.0)
        result = amplify(X, t_peak=T_SPIKE, alpha=5.0, widening_sigma=1.0)
        far_idx = T_SPIKE - 10
        np.testing.assert_allclose(result.values[far_idx], X[far_idx], atol=1e-3)

    def test_widening_sigma_controls_spread(self):
        """Larger sigma → more samples affected around the peak."""
        # Use a non-zero baseline so the multiplicative envelope has visible effect
        X = np.full(N, 2.0, dtype=np.float64)
        X[T_SPIKE] += SPIKE_HEIGHT
        r_narrow = amplify(X, t_peak=T_SPIKE, alpha=2.0, widening_sigma=0.5)
        r_wide = amplify(X, t_peak=T_SPIKE, alpha=2.0, widening_sigma=5.0)
        idx_near = T_SPIKE + 1
        diff_narrow = abs(r_narrow.values[idx_near] - X[idx_near])
        diff_wide = abs(r_wide.values[idx_near] - X[idx_near])
        assert diff_wide > diff_narrow

    def test_alpha_one_is_identity(self):
        X = _spike_signal()
        result = amplify(X, t_peak=T_SPIKE, alpha=1.0)
        np.testing.assert_allclose(result.values, X, atol=1e-12)

    def test_relabel_preserved(self):
        result = amplify(_spike_signal(), t_peak=T_SPIKE, alpha=2.0)
        assert result.relabel.rule_class == "PRESERVED"
        assert result.relabel.new_shape == "spike"

    def test_op_name(self):
        assert amplify(_spike_signal(), t_peak=T_SPIKE, alpha=2.0).op_name == "amplify"

    def test_tier(self):
        assert amplify(_spike_signal(), t_peak=T_SPIKE, alpha=2.0).tier == 2

    def test_t_peak_out_of_range_raises(self):
        X = _spike_signal()
        with pytest.raises(ValueError, match="t_peak"):
            amplify(X, t_peak=N + 10, alpha=2.0)

    def test_widening_sigma_zero_raises(self):
        with pytest.raises(ValueError, match="widening_sigma"):
            amplify(_spike_signal(), t_peak=T_SPIKE, alpha=2.0, widening_sigma=0.0)

    def test_negative_spike_amplified_correctly(self):
        X = _spike_signal(noise_sigma=0.0)
        X[T_SPIKE] = -SPIKE_HEIGHT
        result = amplify(X, t_peak=T_SPIKE, alpha=2.0, widening_sigma=0.5)
        np.testing.assert_allclose(result.values[T_SPIKE], 2.0 * (-SPIKE_HEIGHT), atol=1e-12)

    def test_pre_shape_forwarded(self):
        result = amplify(_spike_signal(), t_peak=T_SPIKE, alpha=2.0, pre_shape="noise")
        assert result.relabel.new_shape == "noise"


# ---------------------------------------------------------------------------
# smear_to_transient
# ---------------------------------------------------------------------------


class TestSmearToTransient:
    def test_relabel_deterministic_transient(self):
        result = smear_to_transient(_spike_signal(), sigma_new=3.0)
        assert result.relabel.rule_class == "DETERMINISTIC"
        assert result.relabel.new_shape == "transient"
        assert result.relabel.needs_resegment is False

    def test_op_name(self):
        assert smear_to_transient(_spike_signal(), sigma_new=3.0).op_name == "smear_to_transient"

    def test_tier(self):
        assert smear_to_transient(_spike_signal(), sigma_new=3.0).tier == 2

    def test_sigma_zero_raises(self):
        with pytest.raises(ValueError, match="sigma_new"):
            smear_to_transient(_spike_signal(), sigma_new=0.0)

    def test_sigma_negative_raises(self):
        with pytest.raises(ValueError):
            smear_to_transient(_spike_signal(), sigma_new=-1.0)

    def test_output_same_length(self):
        X = _spike_signal()
        result = smear_to_transient(X, sigma_new=3.0)
        assert len(result.values) == len(X)

    def test_neighbors_nonzero_after_smear(self):
        """The convolution must spread energy to neighbours of the spike."""
        X = np.zeros(N, dtype=np.float64)
        X[T_SPIKE] = 10.0
        result = smear_to_transient(X, sigma_new=3.0)
        assert abs(result.values[T_SPIKE - 2]) > 1e-6
        assert abs(result.values[T_SPIKE + 2]) > 1e-6

    def test_smear_reduces_peak_sharpness(self):
        """Peak value after smearing should be lower than the original spike."""
        X = np.zeros(N, dtype=np.float64)
        X[T_SPIKE] = 10.0
        result = smear_to_transient(X, sigma_new=3.0)
        assert abs(result.values[T_SPIKE]) < 10.0

    def test_deterministic_shape_always_transient(self):
        """DETERMINISTIC always outputs 'transient' regardless of pre_shape."""
        for pre in ("spike", "noise", "plateau"):
            result = smear_to_transient(_spike_signal(), sigma_new=3.0, pre_shape=pre)
            assert result.relabel.new_shape == "transient"

    def test_caller_signal_not_mutated(self):
        X = _spike_signal()
        orig = X.copy()
        smear_to_transient(X, sigma_new=3.0)
        np.testing.assert_array_equal(X, orig)


# ---------------------------------------------------------------------------
# duplicate
# ---------------------------------------------------------------------------


class TestDuplicate:
    def test_second_spike_at_t_new(self):
        X = _spike_signal(noise_sigma=0.0)
        t_new = 5
        alpha = 0.5
        result = duplicate(X, t_new=t_new, alpha=alpha)
        expected_new = alpha * X[T_SPIKE]
        np.testing.assert_allclose(result.values[t_new], X[t_new] + expected_new, atol=1e-12)

    def test_original_spike_unchanged(self):
        X = _spike_signal(noise_sigma=0.0)
        result = duplicate(X, t_new=5, alpha=0.5)
        np.testing.assert_allclose(result.values[T_SPIKE], X[T_SPIKE], atol=1e-12)

    def test_other_samples_unchanged(self):
        X = _spike_signal(noise_sigma=0.0)
        t_new = 5
        result = duplicate(X, t_new=t_new, alpha=0.5)
        other = [i for i in range(N) if i != t_new]
        np.testing.assert_allclose(result.values[other], X[other], atol=1e-12)

    def test_relabel_reclassify(self):
        result = duplicate(_spike_signal(), t_new=5, alpha=0.5)
        assert result.relabel.rule_class == "RECLASSIFY_VIA_SEGMENTER"
        assert result.relabel.needs_resegment is True

    def test_op_name(self):
        assert duplicate(_spike_signal(), t_new=5, alpha=0.5).op_name == "duplicate"

    def test_tier(self):
        assert duplicate(_spike_signal(), t_new=5, alpha=0.5).tier == 2

    def test_t_new_out_of_range_raises(self):
        with pytest.raises(ValueError, match="t_new"):
            duplicate(_spike_signal(), t_new=N + 5, alpha=0.5)

    def test_alpha_zero_no_second_spike(self):
        X = _spike_signal(noise_sigma=0.0)
        t_new = 5
        result = duplicate(X, t_new=t_new, alpha=0.0)
        np.testing.assert_array_equal(result.values, X)

    def test_pre_shape_forwarded(self):
        result = duplicate(_spike_signal(), t_new=5, alpha=0.5, pre_shape="noise")
        assert result.relabel.new_shape == "noise"

    def test_caller_signal_not_mutated(self):
        X = _spike_signal()
        orig = X.copy()
        duplicate(X, t_new=5, alpha=0.5)
        np.testing.assert_array_equal(X, orig)


# ---------------------------------------------------------------------------
# shift_time
# ---------------------------------------------------------------------------


class TestShiftTime:
    def test_spike_position_moves(self):
        """After shift, the sample with max absolute value should be near t_spike + delta_t."""
        X = np.zeros(N, dtype=np.float64)
        X[T_SPIKE] = SPIKE_HEIGHT
        delta_t = 5
        result = shift_time(X, delta_t=delta_t)
        peak_after = int(np.argmax(np.abs(result.values)))
        assert peak_after == T_SPIKE + delta_t

    def test_relabel_preserved(self):
        result = shift_time(_spike_signal(), delta_t=3)
        assert result.relabel.rule_class == "PRESERVED"
        assert result.relabel.new_shape == "spike"

    def test_op_name(self):
        assert shift_time(_spike_signal(), delta_t=3).op_name == "shift_time"

    def test_tier(self):
        assert shift_time(_spike_signal(), delta_t=3).tier == 2

    def test_delta_t_zero_identity(self):
        X = _spike_signal()
        result = shift_time(X, delta_t=0)
        np.testing.assert_array_equal(result.values, X)

    def test_output_same_length(self):
        X = _spike_signal()
        result = shift_time(X, delta_t=5)
        assert len(result.values) == len(X)

    def test_pre_shape_forwarded(self):
        result = shift_time(_spike_signal(), delta_t=3, pre_shape="noise")
        assert result.relabel.new_shape == "noise"

    def test_short_spike_segment_no_error(self):
        """Near-single-sample spikes (n < 6) must not raise taper_width error."""
        X = np.array([0.0, 0.0, 5.0, 0.0, 0.0])
        result = shift_time(X, delta_t=1)
        assert isinstance(result, Tier2OpResult)
        assert len(result.values) == 5


# ---------------------------------------------------------------------------
# Cross-op / return-type
# ---------------------------------------------------------------------------


class TestCrossOp:
    def test_all_ops_return_tier2_result(self):
        X = _spike_signal()
        ops_results = [
            remove(X),
            clip_cap(X),
            amplify(X, t_peak=T_SPIKE, alpha=2.0),
            smear_to_transient(X, sigma_new=3.0),
            duplicate(X, t_new=5, alpha=0.5),
            shift_time(X, delta_t=3),
        ]
        for r in ops_results:
            assert isinstance(r, Tier2OpResult)

    def test_remove_and_clip_cap_different_mechanisms(self):
        """remove replaces with median; clip_cap replaces with cap value."""
        X = _spike_signal(noise_sigma=0.0)
        r_remove = remove(X, method="hampel")
        r_clip = clip_cap(X, quantile=0.95)
        cap = float(np.quantile(X, 0.95))
        # clip_cap leaves spike at exactly cap; remove leaves it at local median (~0)
        assert abs(r_clip.values[T_SPIKE] - cap) < 1e-6
        assert abs(r_remove.values[T_SPIKE]) < 1.0

    def test_smear_followed_by_clip_cap(self):
        """Composed ops: smear then clip. Both return Tier2OpResult."""
        X = _spike_signal()
        smeared = smear_to_transient(X, sigma_new=3.0)
        clipped = clip_cap(smeared.values, quantile=0.95)
        assert isinstance(clipped, Tier2OpResult)
        assert clipped.op_name == "clip_cap"
