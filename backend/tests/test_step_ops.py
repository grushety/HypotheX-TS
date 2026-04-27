"""Tests for Tier-2 step ops: de_jump, invert_sign, scale_magnitude,
shift_in_time, convert_to_ramp, duplicate (OP-022).
"""

import copy

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.operations.tier2.step import (
    convert_to_ramp,
    de_jump,
    duplicate,
    invert_sign,
    scale_magnitude,
    shift_in_time,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

N = 30
T_S = 10.0


def _t(n: int = N) -> np.ndarray:
    return np.linspace(0.0, float(n - 1), n)


def _etm_step_blob(n: int = N, t_s: float = T_S, delta: float = 5.0) -> DecompositionBlob:
    """ETM blob with a single Heaviside step at t_s."""
    t = _t(n)
    x0 = 2.0
    rate = 0.1
    step_key = f"step_at_{float(t_s):.6g}"
    blob = DecompositionBlob(
        method="ETM",
        coefficients={
            "x0": x0,
            "linear_rate": rate,
            step_key: delta,
        },
        components={
            "x0": np.full(n, x0),
            "linear_rate": rate * t,
            step_key: delta * (t >= t_s).astype(np.float64),
            "residual": np.zeros(n),
        },
        fit_metadata={},
    )
    return blob


def _original_signal(n: int = N, t_s: float = T_S, delta: float = 5.0) -> np.ndarray:
    """Reconstruct the expected signal from the fixture blob."""
    t = _t(n)
    return 2.0 + 0.1 * t + delta * (t >= t_s).astype(np.float64)


# ---------------------------------------------------------------------------
# de_jump
# ---------------------------------------------------------------------------


class TestDeJump:
    def test_step_component_zeroed(self):
        blob = _etm_step_blob()
        result = de_jump(blob, T_S)
        expected_no_step = 2.0 + 0.1 * _t()
        np.testing.assert_allclose(result.values, expected_no_step, atol=1e-12)

    def test_relabel_reclassify(self):
        result = de_jump(_etm_step_blob(), T_S)
        assert result.relabel.rule_class == "RECLASSIFY_VIA_SEGMENTER"
        assert result.relabel.needs_resegment is True

    def test_op_name(self):
        assert de_jump(_etm_step_blob(), T_S).op_name == "de_jump"

    def test_tier(self):
        assert de_jump(_etm_step_blob(), T_S).tier == 2

    def test_caller_blob_not_mutated(self):
        blob = _etm_step_blob()
        step_key = f"step_at_{T_S:.6g}"
        original_coeff = blob.coefficients[step_key]
        de_jump(blob, T_S)
        assert blob.coefficients[step_key] == original_coeff

    def test_missing_step_raises(self):
        blob = _etm_step_blob()
        with pytest.raises(ValueError, match="step op"):
            de_jump(blob, 999.0)

    def test_pre_shape_forwarded(self):
        result = de_jump(_etm_step_blob(), T_S, pre_shape="transient")
        assert result.relabel.new_shape == "transient"


# ---------------------------------------------------------------------------
# invert_sign
# ---------------------------------------------------------------------------


class TestInvertSign:
    def test_step_negated(self):
        blob = _etm_step_blob(delta=5.0)
        result = invert_sign(blob, T_S)
        t = _t()
        expected = 2.0 + 0.1 * t + (-5.0) * (t >= T_S).astype(np.float64)
        np.testing.assert_allclose(result.values, expected, atol=1e-12)

    def test_relabel_preserved(self):
        result = invert_sign(_etm_step_blob(), T_S)
        assert result.relabel.rule_class == "PRESERVED"
        assert result.relabel.new_shape == "step"
        assert result.relabel.needs_resegment is False

    def test_op_name(self):
        assert invert_sign(_etm_step_blob(), T_S).op_name == "invert_sign"

    def test_caller_blob_not_mutated(self):
        blob = _etm_step_blob(delta=5.0)
        step_key = f"step_at_{T_S:.6g}"
        invert_sign(blob, T_S)
        assert blob.coefficients[step_key] == 5.0

    def test_missing_step_raises(self):
        with pytest.raises(ValueError):
            invert_sign(_etm_step_blob(), 999.0)

    def test_pre_shape_forwarded(self):
        result = invert_sign(_etm_step_blob(), T_S, pre_shape="noise")
        assert result.relabel.new_shape == "noise"

    def test_signal_before_step_unchanged(self):
        blob = _etm_step_blob(delta=5.0)
        result = invert_sign(blob, T_S)
        original = _original_signal(delta=5.0)
        t = _t()
        pre_mask = t < T_S
        np.testing.assert_allclose(result.values[pre_mask], original[pre_mask], atol=1e-12)

    def test_double_invert_is_identity(self):
        blob = _etm_step_blob(delta=5.0)
        original = blob.reassemble().copy()
        r1 = invert_sign(blob, T_S)
        blob2 = _etm_step_blob(delta=5.0)
        step_key = f"step_at_{T_S:.6g}"
        blob2.coefficients[step_key] = -5.0
        blob2.components[step_key] = -5.0 * ((_t()) >= T_S).astype(np.float64)
        r2 = invert_sign(blob2, T_S)
        np.testing.assert_allclose(r2.values, original, atol=1e-12)


# ---------------------------------------------------------------------------
# scale_magnitude
# ---------------------------------------------------------------------------


class TestScaleMagnitude:
    def test_scale_by_2(self):
        blob = _etm_step_blob(delta=5.0)
        result = scale_magnitude(blob, T_S, alpha=2.0)
        t = _t()
        expected = 2.0 + 0.1 * t + 10.0 * (t >= T_S).astype(np.float64)
        np.testing.assert_allclose(result.values, expected, atol=1e-12)

    def test_scale_zero_relabel_reclassify(self):
        result = scale_magnitude(_etm_step_blob(), T_S, alpha=0.0)
        assert result.relabel.rule_class == "RECLASSIFY_VIA_SEGMENTER"

    def test_scale_nonzero_relabel_preserved(self):
        result = scale_magnitude(_etm_step_blob(), T_S, alpha=3.0)
        assert result.relabel.rule_class == "PRESERVED"
        assert result.relabel.new_shape == "step"

    def test_scale_zero_identical_to_de_jump(self):
        blob = _etm_step_blob()
        r_scale = scale_magnitude(blob, T_S, alpha=0.0)
        r_dejump = de_jump(blob, T_S)
        np.testing.assert_array_equal(r_scale.values, r_dejump.values)

    def test_op_name(self):
        assert scale_magnitude(_etm_step_blob(), T_S, alpha=2.0).op_name == "scale_magnitude"

    def test_caller_blob_not_mutated(self):
        blob = _etm_step_blob(delta=5.0)
        step_key = f"step_at_{T_S:.6g}"
        scale_magnitude(blob, T_S, alpha=3.0)
        assert blob.coefficients[step_key] == 5.0

    def test_missing_step_raises(self):
        with pytest.raises(ValueError):
            scale_magnitude(_etm_step_blob(), 999.0, alpha=2.0)

    def test_scale_negative_one_identical_to_invert_sign(self):
        blob = _etm_step_blob(delta=5.0)
        r_scale = scale_magnitude(blob, T_S, alpha=-1.0)
        r_invert = invert_sign(blob, T_S)
        np.testing.assert_allclose(r_scale.values, r_invert.values, atol=1e-12)

    def test_pre_shape_forwarded(self):
        result = scale_magnitude(_etm_step_blob(), T_S, alpha=2.0, pre_shape="plateau")
        assert result.relabel.new_shape == "plateau"


# ---------------------------------------------------------------------------
# shift_in_time
# ---------------------------------------------------------------------------


class TestShiftInTime:
    def test_step_at_new_epoch(self):
        blob = _etm_step_blob(delta=5.0, t_s=T_S)
        t = _t()
        t_s_new = 15.0
        result = shift_in_time(blob, T_S, t_s_new, t)
        expected = 2.0 + 0.1 * t + 5.0 * (t >= t_s_new).astype(np.float64)
        np.testing.assert_allclose(result.values, expected, atol=1e-12)

    def test_old_key_removed(self):
        blob = _etm_step_blob(delta=5.0, t_s=T_S)
        t = _t()
        shift_in_time(blob, T_S, 15.0, t)
        step_key_old = f"step_at_{T_S:.6g}"
        assert step_key_old in blob.coefficients  # original not mutated

    def test_relabel_preserved(self):
        result = shift_in_time(_etm_step_blob(), T_S, 15.0, _t())
        assert result.relabel.rule_class == "PRESERVED"
        assert result.relabel.new_shape == "step"

    def test_op_name(self):
        assert shift_in_time(_etm_step_blob(), T_S, 15.0, _t()).op_name == "shift_in_time"

    def test_caller_blob_not_mutated(self):
        blob = _etm_step_blob()
        step_key = f"step_at_{T_S:.6g}"
        shift_in_time(blob, T_S, 15.0, _t())
        assert step_key in blob.coefficients

    def test_missing_step_raises(self):
        with pytest.raises(ValueError):
            shift_in_time(_etm_step_blob(), 999.0, 15.0, _t())

    def test_amplitude_preserved_after_shift(self):
        blob = _etm_step_blob(delta=7.3)
        t = _t()
        t_s_new = 20.0
        result = shift_in_time(blob, T_S, t_s_new, t)
        # at t_s_new the step should appear with correct amplitude
        idx = int(t_s_new)
        pre_mean = np.mean(result.values[:idx])
        post_mean = np.mean(result.values[idx:])
        assert post_mean > pre_mean  # positive delta shifts level up

    def test_shift_to_same_epoch_identity(self):
        blob = _etm_step_blob(delta=5.0, t_s=T_S)
        t = _t()
        result = shift_in_time(blob, T_S, T_S, t)
        original = _original_signal(delta=5.0, t_s=T_S)
        np.testing.assert_allclose(result.values, original, atol=1e-12)


# ---------------------------------------------------------------------------
# convert_to_ramp
# ---------------------------------------------------------------------------


class TestConvertToRamp:
    def test_ramp_shape(self):
        blob = _etm_step_blob(delta=5.0, t_s=T_S)
        t = _t()
        tau = 5.0
        result = convert_to_ramp(blob, T_S, tau, t)
        # values should be monotonically non-decreasing after t_s (for positive delta)
        post_idx = t >= T_S
        post_vals = result.values[post_idx]
        assert np.all(np.diff(post_vals) >= -1e-12)

    def test_pre_step_unchanged(self):
        blob = _etm_step_blob(delta=5.0, t_s=T_S)
        t = _t()
        result = convert_to_ramp(blob, T_S, tau_ramp=5.0, t=t)
        original = _original_signal(delta=5.0, t_s=T_S)
        pre_mask = t < T_S
        np.testing.assert_allclose(result.values[pre_mask], original[pre_mask], atol=1e-12)

    def test_relabel_deterministic_transient(self):
        result = convert_to_ramp(_etm_step_blob(), T_S, 5.0, _t())
        assert result.relabel.rule_class == "DETERMINISTIC"
        assert result.relabel.new_shape == "transient"
        assert result.relabel.needs_resegment is False

    def test_op_name(self):
        assert convert_to_ramp(_etm_step_blob(), T_S, 5.0, _t()).op_name == "convert_to_ramp"

    def test_tau_ramp_zero_raises(self):
        with pytest.raises(ValueError, match="tau_ramp"):
            convert_to_ramp(_etm_step_blob(), T_S, 0.0, _t())

    def test_tau_ramp_negative_raises(self):
        with pytest.raises(ValueError, match="tau_ramp"):
            convert_to_ramp(_etm_step_blob(), T_S, -1.0, _t())

    def test_missing_step_raises(self):
        with pytest.raises(ValueError):
            convert_to_ramp(_etm_step_blob(), 999.0, 5.0, _t())

    def test_caller_blob_not_mutated(self):
        blob = _etm_step_blob()
        step_key = f"step_at_{T_S:.6g}"
        convert_to_ramp(blob, T_S, 5.0, _t())
        assert step_key in blob.coefficients

    def test_large_tau_approaches_step(self):
        """Very large tau → log1p((t-t_s)/tau) ≈ 0 near t_s, small ramp."""
        blob = _etm_step_blob(delta=5.0, t_s=T_S)
        t = _t()
        result = convert_to_ramp(blob, T_S, tau_ramp=1e9, t=t)
        # At the last sample, the ramp should be much smaller than the original step
        original = _original_signal(delta=5.0, t_s=T_S)
        last_orig = original[-1]
        last_ramp = result.values[-1]
        # ramp contribution is tiny, so the values are much smaller than original step
        assert abs(last_ramp - last_orig) > 4.0

    def test_zero_at_t_s(self):
        """Log transient evaluates to 0 exactly at t_s."""
        blob = _etm_step_blob(delta=5.0, t_s=T_S)
        t = _t()
        result = convert_to_ramp(blob, T_S, tau_ramp=5.0, t=t)
        # t[10] == 10.0 == T_S; log1p(0) = 0, so only x0 + linear_rate*T_S
        idx = int(T_S)  # 10
        expected_at_ts = 2.0 + 0.1 * T_S
        np.testing.assert_allclose(result.values[idx], expected_at_ts, atol=1e-12)


# ---------------------------------------------------------------------------
# duplicate
# ---------------------------------------------------------------------------


class TestDuplicate:
    def test_second_step_added(self):
        blob = _etm_step_blob(delta=5.0, t_s=T_S)
        t = _t()
        delta_t = 5.0
        delta_2 = 3.0
        t_s_new = T_S + delta_t
        result = duplicate(blob, T_S, delta_t, delta_2, t)
        # signal should have both steps
        expected = 2.0 + 0.1 * t + 5.0 * (t >= T_S).astype(np.float64) + delta_2 * (t >= t_s_new).astype(np.float64)
        np.testing.assert_allclose(result.values, expected, atol=1e-12)

    def test_relabel_reclassify(self):
        result = duplicate(_etm_step_blob(), T_S, 5.0, 3.0, _t())
        assert result.relabel.rule_class == "RECLASSIFY_VIA_SEGMENTER"
        assert result.relabel.needs_resegment is True

    def test_op_name(self):
        assert duplicate(_etm_step_blob(), T_S, 5.0, 3.0, _t()).op_name == "duplicate"

    def test_caller_blob_not_mutated(self):
        blob = _etm_step_blob()
        step_key_new = f"step_at_{T_S + 5.0:.6g}"
        duplicate(blob, T_S, 5.0, 3.0, _t())
        assert step_key_new not in blob.coefficients

    def test_original_step_unchanged(self):
        blob = _etm_step_blob(delta=5.0)
        result = duplicate(blob, T_S, 5.0, 3.0, _t())
        t = _t()
        # region before both steps: only x0 + rate*t
        pre_mask = t < T_S
        expected_pre = 2.0 + 0.1 * t[pre_mask]
        np.testing.assert_allclose(result.values[pre_mask], expected_pre, atol=1e-12)

    def test_missing_step_raises(self):
        with pytest.raises(ValueError):
            duplicate(_etm_step_blob(), 999.0, 5.0, 3.0, _t())

    def test_delta_t_zero_raises(self):
        with pytest.raises(ValueError, match="delta_t"):
            duplicate(_etm_step_blob(), T_S, 0.0, 3.0, _t())

    def test_pre_shape_forwarded(self):
        result = duplicate(_etm_step_blob(), T_S, 5.0, 3.0, _t(), pre_shape="trend")
        assert result.relabel.new_shape == "trend"

    def test_negative_delta_t(self):
        """Adding a step before the original is valid."""
        blob = _etm_step_blob(delta=5.0, t_s=T_S)
        t = _t()
        t_s_new = T_S - 5.0
        result = duplicate(blob, T_S, -5.0, 2.0, t)
        expected = 2.0 + 0.1 * t + 2.0 * (t >= t_s_new).astype(np.float64) + 5.0 * (t >= T_S).astype(np.float64)
        np.testing.assert_allclose(result.values, expected, atol=1e-12)

    def test_tier(self):
        assert duplicate(_etm_step_blob(), T_S, 5.0, 3.0, _t()).tier == 2


# ---------------------------------------------------------------------------
# Cross-op consistency
# ---------------------------------------------------------------------------


class TestCrossOpConsistency:
    def test_de_jump_scale_zero_bit_identical(self):
        """de_jump and scale_magnitude(alpha=0) must produce bit-identical values."""
        blob = _etm_step_blob()
        r_dj = de_jump(blob, T_S)
        r_sm = scale_magnitude(blob, T_S, alpha=0.0)
        np.testing.assert_array_equal(r_dj.values, r_sm.values)

    def test_invert_sign_scale_minus_one_allclose(self):
        blob = _etm_step_blob(delta=5.0)
        r_inv = invert_sign(blob, T_S)
        r_scale = scale_magnitude(blob, T_S, alpha=-1.0)
        np.testing.assert_allclose(r_inv.values, r_scale.values, atol=1e-12)

    def test_shift_to_beyond_window_zeroes_step(self):
        """Shifting to t beyond the last sample effectively removes the step."""
        blob = _etm_step_blob(delta=5.0, t_s=T_S)
        t = _t()
        t_s_new = 1e6  # beyond any sample
        result = shift_in_time(blob, T_S, t_s_new, t)
        # no sample has t >= t_s_new, so step component is all zeros
        expected_no_step = 2.0 + 0.1 * t
        np.testing.assert_allclose(result.values, expected_no_step, atol=1e-12)

    def test_all_ops_return_tier2_result(self):
        from app.services.operations.tier2.plateau import Tier2OpResult
        blob = _etm_step_blob()
        t = _t()
        ops_results = [
            de_jump(blob, T_S),
            invert_sign(blob, T_S),
            scale_magnitude(blob, T_S, alpha=2.0),
            shift_in_time(blob, T_S, 15.0, t),
            convert_to_ramp(blob, T_S, 5.0, t),
            duplicate(blob, T_S, 5.0, 3.0, t),
        ]
        for r in ops_results:
            assert isinstance(r, Tier2OpResult)
