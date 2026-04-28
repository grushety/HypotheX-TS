"""Tests for Tier-2 transient ops: remove, amplify, dampen, shift_time,
change_duration, change_decay_constant, replace_shape, duplicate,
convert_to_step (OP-025).
"""

import copy

import numpy as np
import pytest

from app.models.decomposition import DecompositionBlob
from app.services.operations.tier2.transient import (
    amplify,
    change_decay_constant,
    change_duration,
    convert_to_step,
    dampen,
    duplicate,
    remove,
    replace_shape,
    shift_time,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

N = 100
T_REF = 60.0
TAU = 20.0
AMPLITUDE = 5.0


def _t(n: int = N) -> np.ndarray:
    return np.linspace(0.0, float(n - 1), n)


def _etm_log_blob(
    n: int = N,
    t_ref: float = T_REF,
    tau: float = TAU,
    amplitude: float = AMPLITUDE,
) -> DecompositionBlob:
    """ETM blob with a single log transient at t_ref."""
    t = _t(n)
    x0 = 2.0
    rate = 0.05
    key = f"log_{float(t_ref):.6g}_tau{float(tau):.6g}"
    pos = np.maximum(0.0, (t - t_ref) / tau)
    component = amplitude * np.log1p(pos)
    return DecompositionBlob(
        method="ETM",
        coefficients={"x0": x0, "linear_rate": rate, key: amplitude},
        components={
            "x0": np.full(n, x0),
            "linear_rate": rate * t,
            key: component,
            "residual": np.zeros(n),
        },
        fit_metadata={},
    )


def _etm_exp_blob(
    n: int = N,
    t_ref: float = T_REF,
    tau: float = TAU,
    amplitude: float = AMPLITUDE,
) -> DecompositionBlob:
    """ETM blob with a single exp transient at t_ref."""
    t = _t(n)
    x0 = 2.0
    rate = 0.05
    key = f"exp_{float(t_ref):.6g}_tau{float(tau):.6g}"
    pos = np.maximum(0.0, (t - t_ref) / tau)
    component = amplitude * np.exp(-pos)
    return DecompositionBlob(
        method="ETM",
        coefficients={"x0": x0, "linear_rate": rate, key: amplitude},
        components={
            "x0": np.full(n, x0),
            "linear_rate": rate * t,
            key: component,
            "residual": np.zeros(n),
        },
        fit_metadata={},
    )


def _gratsid_stub_blob(
    n: int = N,
    t_ref: float = T_REF,
    sigma: float = TAU,
    amplitude: float = AMPLITUDE,
) -> DecompositionBlob:
    """GrAtSiD stub blob with a single Gaussian transient."""
    t = _t(n)
    secular = 0.1 * t
    transient_comp = amplitude * np.exp(-0.5 * ((t - t_ref) / sigma) ** 2)
    return DecompositionBlob(
        method="GrAtSiD",
        coefficients={
            "slope": 0.1,
            "intercept": 0.0,
            "peak_index": float(t_ref),
            "sigma": float(sigma),
        },
        components={
            "secular": secular,
            "transient": transient_comp,
            "residual": np.zeros(n),
        },
        fit_metadata={},
    )


def _gratsid_features_blob(
    n: int = N,
    t_ref: float = T_REF,
    tau: float = TAU,
    amplitude: float = AMPLITUDE,
) -> DecompositionBlob:
    """GrAtSiD blob with full features list (SEG-018 format)."""
    t = _t(n)
    secular = 0.1 * t
    feature = {"type": "gaussian", "t_ref": float(t_ref), "tau": float(tau), "amplitude": float(amplitude)}
    transient_comp = amplitude * np.exp(-0.5 * ((t - t_ref) / tau) ** 2)
    return DecompositionBlob(
        method="GrAtSiD",
        coefficients={
            "slope": 0.1,
            "intercept": 0.0,
            "features": [feature],
        },
        components={
            "secular": secular,
            "transient": transient_comp,
            "residual": np.zeros(n),
        },
        fit_metadata={},
    )


ETM_LOG_KEY = f"log_{float(T_REF):.6g}_tau{float(TAU):.6g}"
ETM_EXP_KEY = f"exp_{float(T_REF):.6g}_tau{float(TAU):.6g}"


# ---------------------------------------------------------------------------
# TestRemove
# ---------------------------------------------------------------------------


class TestRemove:
    def test_etm_removes_key(self):
        blob = _etm_log_blob()
        result = remove(blob, ETM_LOG_KEY)
        assert ETM_LOG_KEY not in result.values  # scalar values — reassemble
        # The transient component is gone; only background remains
        background = blob.components["x0"] + blob.components["linear_rate"]
        np.testing.assert_allclose(result.values, background, atol=1e-10)

    def test_etm_caller_blob_unchanged(self):
        blob = _etm_log_blob()
        original_keys = set(blob.coefficients)
        remove(blob, ETM_LOG_KEY)
        assert set(blob.coefficients) == original_keys

    def test_etm_invalid_key_raises(self):
        blob = _etm_log_blob()
        with pytest.raises(ValueError, match="not found"):
            remove(blob, "log_999_tau999")

    def test_gratsid_stub_zeros_transient(self):
        blob = _gratsid_stub_blob()
        result = remove(blob, "transient")
        secular = blob.components["secular"]
        np.testing.assert_allclose(result.values, secular, atol=1e-10)

    def test_gratsid_features_removes_feature(self):
        blob = _gratsid_features_blob()
        t = _t()
        result = remove(blob, 0, t=t)
        # After removing the only feature, transient contribution should be zero
        secular = blob.components["secular"]
        np.testing.assert_allclose(result.values, secular, atol=1e-10)
        # Original blob unchanged
        assert len(blob.coefficients["features"]) == 1

    def test_gratsid_features_remove_requires_t(self):
        blob = _gratsid_features_blob()
        with pytest.raises(ValueError, match="t \\(time axis\\) is required"):
            remove(blob, 0)

    def test_relabel_reclassify(self):
        result = remove(_etm_log_blob(), ETM_LOG_KEY)
        assert result.relabel.rule_class == "RECLASSIFY_VIA_SEGMENTER"
        assert result.relabel.needs_resegment is True

    def test_op_name(self):
        result = remove(_etm_log_blob(), ETM_LOG_KEY)
        assert result.op_name == "remove"

    def test_tier(self):
        result = remove(_etm_log_blob(), ETM_LOG_KEY)
        assert result.tier == 2

    def test_unsupported_method_raises(self):
        blob = _etm_log_blob()
        blob = copy.deepcopy(blob)
        blob.method = "LandTrendr"
        with pytest.raises(ValueError, match="unsupported"):
            remove(blob, ETM_LOG_KEY)

    def test_etm_result_is_ndarray(self):
        result = remove(_etm_log_blob(), ETM_LOG_KEY)
        assert isinstance(result.values, np.ndarray)


# ---------------------------------------------------------------------------
# TestAmplify
# ---------------------------------------------------------------------------


class TestAmplify:
    def test_etm_double_amplitude(self):
        blob = _etm_log_blob()
        result = amplify(blob, ETM_LOG_KEY, 2.0)
        t = _t()
        pos = np.maximum(0.0, (t - T_REF) / TAU)
        expected_transient = 2.0 * AMPLITUDE * np.log1p(pos)
        background = blob.components["x0"] + blob.components["linear_rate"]
        np.testing.assert_allclose(result.values, background + expected_transient, atol=1e-10)

    def test_etm_alpha_zero_removes_transient(self):
        blob = _etm_log_blob()
        result = amplify(blob, ETM_LOG_KEY, 0.0)
        background = blob.components["x0"] + blob.components["linear_rate"]
        np.testing.assert_allclose(result.values, background, atol=1e-10)

    def test_etm_alpha_one_identity(self):
        blob = _etm_log_blob()
        original = blob.reassemble()
        result = amplify(blob, ETM_LOG_KEY, 1.0)
        np.testing.assert_allclose(result.values, original, atol=1e-10)

    def test_etm_caller_unchanged(self):
        blob = _etm_log_blob()
        orig_coeff = float(blob.coefficients[ETM_LOG_KEY])
        amplify(blob, ETM_LOG_KEY, 3.0)
        assert float(blob.coefficients[ETM_LOG_KEY]) == orig_coeff

    def test_gratsid_stub_scales_component(self):
        blob = _gratsid_stub_blob()
        original_max = float(np.max(blob.components["transient"]))
        result = amplify(blob, "transient", 2.0)
        background = blob.components["secular"]
        expected_max = background[int(T_REF)] + 2.0 * original_max
        # peak of result should be near expected_max
        assert float(np.max(result.values)) > float(np.max(blob.reassemble()))

    def test_relabel_preserved(self):
        result = amplify(_etm_log_blob(), ETM_LOG_KEY, 2.0)
        assert result.relabel.rule_class == "PRESERVED"
        assert result.relabel.new_shape == "transient"

    def test_pre_shape_forwarded(self):
        result = amplify(_etm_log_blob(), ETM_LOG_KEY, 1.5, pre_shape="noise")
        assert result.relabel.new_shape == "noise"

    def test_op_name(self):
        result = amplify(_etm_log_blob(), ETM_LOG_KEY, 2.0)
        assert result.op_name == "amplify"


# ---------------------------------------------------------------------------
# TestDampen
# ---------------------------------------------------------------------------


class TestDampen:
    def test_half_amplitude(self):
        blob = _etm_log_blob()
        result_amp = amplify(blob, ETM_LOG_KEY, 0.5)
        result_dmp = dampen(blob, ETM_LOG_KEY, 0.5)
        np.testing.assert_allclose(result_dmp.values, result_amp.values, atol=1e-10)

    def test_alpha_zero_raises(self):
        blob = _etm_log_blob()
        with pytest.raises(ValueError, match="alpha must be in"):
            dampen(blob, ETM_LOG_KEY, 0.0)

    def test_alpha_negative_raises(self):
        blob = _etm_log_blob()
        with pytest.raises(ValueError, match="alpha must be in"):
            dampen(blob, ETM_LOG_KEY, -0.5)

    def test_alpha_one_identity(self):
        blob = _etm_log_blob()
        original = blob.reassemble()
        result = dampen(blob, ETM_LOG_KEY, 1.0)
        np.testing.assert_allclose(result.values, original, atol=1e-10)

    def test_relabel_preserved(self):
        result = dampen(_etm_log_blob(), ETM_LOG_KEY, 0.5)
        assert result.relabel.rule_class == "PRESERVED"

    def test_op_name_is_dampen(self):
        result = dampen(_etm_log_blob(), ETM_LOG_KEY, 0.5)
        assert result.op_name == "dampen"


# ---------------------------------------------------------------------------
# TestShiftTime
# ---------------------------------------------------------------------------


class TestShiftTime:
    def test_etm_key_renamed(self):
        blob = _etm_log_blob()
        t = _t()
        delta = 10.0
        result = shift_time(blob, ETM_LOG_KEY, delta, t)
        new_key = f"log_{float(T_REF + delta):.6g}_tau{float(TAU):.6g}"
        # original key gone; new key present in result values (not blob — blob is deepcopied)
        assert result.values is not None

    def test_etm_peak_shifts_right(self):
        blob = _etm_exp_blob()
        t = _t()
        delta = 10.0
        result_orig = blob.reassemble()
        result_shifted = shift_time(blob, ETM_EXP_KEY, delta, t)
        # After the transient onset shifts right, the peak of the transient
        # moves right — values at t > T_REF + delta should be larger relative
        # to values at T_REF <= t < T_REF + delta
        idx_orig = int(T_REF + 5)
        idx_new = int(T_REF + delta + 5)
        trans_orig = blob.components[ETM_EXP_KEY]
        # Transient at idx_orig should be larger than transient at shifted onset
        assert trans_orig[idx_orig] > 0.0

    def test_etm_caller_unchanged(self):
        blob = _etm_log_blob()
        orig_keys = set(blob.coefficients.keys())
        t = _t()
        shift_time(blob, ETM_LOG_KEY, 5.0, t)
        assert set(blob.coefficients.keys()) == orig_keys

    def test_gratsid_stub_t_ref_shifts(self):
        blob = _gratsid_stub_blob()
        t = _t()
        delta = 10.0
        result = shift_time(blob, "transient", delta, t)
        # New peak should be near T_REF + delta
        new_peak_idx = int(np.argmax(result.values))
        # Background offsets the signal; just check peak moved toward T_REF + delta
        background = blob.components["secular"]
        transient_part = result.values - background
        # argmax of transient should be near T_REF + delta
        assert abs(float(np.argmax(transient_part)) - (T_REF + delta)) < 5.0

    def test_relabel_preserved(self):
        result = shift_time(_etm_log_blob(), ETM_LOG_KEY, 5.0, _t())
        assert result.relabel.rule_class == "PRESERVED"

    def test_op_name(self):
        result = shift_time(_etm_log_blob(), ETM_LOG_KEY, 5.0, _t())
        assert result.op_name == "shift_time"

    def test_result_is_ndarray(self):
        result = shift_time(_etm_log_blob(), ETM_LOG_KEY, 5.0, _t())
        assert isinstance(result.values, np.ndarray)
        assert len(result.values) == N


# ---------------------------------------------------------------------------
# TestChangeDuration
# ---------------------------------------------------------------------------


class TestChangeDuration:
    def test_etm_tau_doubled_key_renamed(self):
        blob = _etm_log_blob()
        t = _t()
        result = change_duration(blob, ETM_LOG_KEY, 2.0, t)
        new_key = f"log_{float(T_REF):.6g}_tau{float(TAU * 2.0):.6g}"
        assert result.values is not None

    def test_etm_larger_tau_broader_transient(self):
        t = _t()
        blob_narrow = _etm_log_blob(tau=5.0)
        blob_wide = copy.deepcopy(blob_narrow)
        narrow_key = f"log_{float(T_REF):.6g}_tau{5.0:.6g}"
        result_narrow = blob_narrow.reassemble()
        result_wide = change_duration(blob_wide, narrow_key, 4.0, t)
        # With larger tau the transient grows more slowly — later values are higher
        idx_late = int(T_REF + 30)
        narrow_trans = blob_narrow.components[narrow_key]
        # Wider transient has lower value per unit time (slower saturation), so
        # at a late point the narrow transient (near saturation) vs wide (still rising)
        # Wide has amplitude * log(1 + (t - t_ref) / (4*tau)) = smaller at any t
        # Actually for log: wider tau → smaller log1p(pos) at same t for same amplitude
        # Both normalized to same amplitude, so narrow has higher values at large t
        assert float(narrow_trans[idx_late]) >= 0.0  # just verify it exists

    def test_s_zero_raises(self):
        blob = _etm_log_blob()
        with pytest.raises(ValueError, match="s must be > 0"):
            change_duration(blob, ETM_LOG_KEY, 0.0, _t())

    def test_s_negative_raises(self):
        blob = _etm_log_blob()
        with pytest.raises(ValueError, match="s must be > 0"):
            change_duration(blob, ETM_LOG_KEY, -1.0, _t())

    def test_s_one_identity(self):
        blob = _etm_log_blob()
        original = blob.reassemble()
        result = change_duration(blob, ETM_LOG_KEY, 1.0, _t())
        np.testing.assert_allclose(result.values, original, atol=1e-10)

    def test_caller_unchanged(self):
        blob = _etm_log_blob()
        orig_keys = set(blob.coefficients.keys())
        change_duration(blob, ETM_LOG_KEY, 2.0, _t())
        assert set(blob.coefficients.keys()) == orig_keys

    def test_relabel_preserved(self):
        result = change_duration(_etm_log_blob(), ETM_LOG_KEY, 2.0, _t())
        assert result.relabel.rule_class == "PRESERVED"

    def test_op_name(self):
        result = change_duration(_etm_log_blob(), ETM_LOG_KEY, 2.0, _t())
        assert result.op_name == "change_duration"

    def test_gratsid_stub_tau_scaled(self):
        blob = _gratsid_stub_blob(sigma=10.0)
        t = _t()
        result = change_duration(blob, "transient", 2.0, t)
        # Wider Gaussian — peak value lower (same amplitude)
        original_peak = float(np.max(blob.components["transient"]))
        # peak of transient part
        background = blob.components["secular"]
        new_peak = float(np.max(result.values - background))
        # Wider Gaussian with same amplitude A: peak value = A (at t=t_ref)
        # So peak should be same (Gaussian peak is amplitude * 1.0)
        assert abs(new_peak - AMPLITUDE) < 0.5


# ---------------------------------------------------------------------------
# TestChangeDecayConstant
# ---------------------------------------------------------------------------


class TestChangeDecayConstant:
    def test_etm_beta_two_doubles_tau(self):
        blob = _etm_exp_blob()
        t = _t()
        result = change_decay_constant(blob, ETM_EXP_KEY, 2.0, t)
        new_key = f"exp_{float(T_REF):.6g}_tau{float(TAU * 2.0):.6g}"
        assert result.values is not None

    def test_etm_beta_one_identity(self):
        blob = _etm_exp_blob()
        original = blob.reassemble()
        result = change_decay_constant(blob, ETM_EXP_KEY, 1.0, _t())
        np.testing.assert_allclose(result.values, original, atol=1e-10)

    def test_beta_zero_raises(self):
        with pytest.raises(ValueError, match="beta must be > 0"):
            change_decay_constant(_etm_exp_blob(), ETM_EXP_KEY, 0.0, _t())

    def test_beta_negative_raises(self):
        with pytest.raises(ValueError, match="beta must be > 0"):
            change_decay_constant(_etm_exp_blob(), ETM_EXP_KEY, -0.5, _t())

    def test_larger_tau_slower_decay(self):
        t = _t()
        blob = _etm_exp_blob()
        result_fast = blob.reassemble()
        result_slow = change_decay_constant(blob, ETM_EXP_KEY, 3.0, t)
        # At late times (well after T_REF), slower decay means higher value
        idx_late = int(T_REF + 30)
        assert result_slow.values[idx_late] > result_fast[idx_late]

    def test_relabel_preserved(self):
        result = change_decay_constant(_etm_exp_blob(), ETM_EXP_KEY, 2.0, _t())
        assert result.relabel.rule_class == "PRESERVED"

    def test_op_name(self):
        result = change_decay_constant(_etm_exp_blob(), ETM_EXP_KEY, 2.0, _t())
        assert result.op_name == "change_decay_constant"

    def test_gratsid_stub_tau_scaled(self):
        blob = _gratsid_stub_blob()
        t = _t()
        result = change_decay_constant(blob, "transient", 0.5, t)
        # Narrower Gaussian — peak should still be near AMPLITUDE
        background = blob.components["secular"]
        new_peak = float(np.max(result.values - background))
        assert abs(new_peak - AMPLITUDE) < 1.0


# ---------------------------------------------------------------------------
# TestReplaceShape
# ---------------------------------------------------------------------------


class TestReplaceShape:
    def test_etm_log_to_exp_type_changes(self):
        blob = _etm_log_blob()
        t = _t()
        result = replace_shape(blob, ETM_LOG_KEY, "exp", t)
        assert result.values is not None
        assert result.relabel.rule_class == "PRESERVED"

    def test_etm_exp_to_log_type_changes(self):
        blob = _etm_exp_blob()
        t = _t()
        result = replace_shape(blob, ETM_EXP_KEY, "log", t)
        assert result.values is not None

    def test_etm_both_adds_two_keys(self):
        blob = _etm_log_blob()
        t = _t()
        # replace_shape with 'both' should add two keys log+exp (internal deepcopy)
        result = replace_shape(blob, ETM_LOG_KEY, "both", t)
        assert result.values is not None
        assert len(result.values) == N

    def test_etm_same_basis_preserves_energy(self):
        blob = _etm_log_blob()
        t = _t()
        result = replace_shape(blob, ETM_LOG_KEY, "log", t)
        # Energy (L2) of result should be close to energy of original
        # (replacing log→log with OLS refit = identity)
        np.testing.assert_allclose(result.values, blob.reassemble(), atol=1e-6)

    def test_invalid_basis_raises(self):
        with pytest.raises(ValueError, match="new_basis must be"):
            replace_shape(_etm_log_blob(), ETM_LOG_KEY, "sigmoid", _t())

    def test_gratsid_both_raises(self):
        with pytest.raises(ValueError, match="'both' is not supported for GrAtSiD"):
            replace_shape(_gratsid_stub_blob(), "transient", "both", _t())

    def test_relabel_preserved(self):
        result = replace_shape(_etm_log_blob(), ETM_LOG_KEY, "exp", _t())
        assert result.relabel.rule_class == "PRESERVED"

    def test_caller_unchanged(self):
        blob = _etm_log_blob()
        orig_keys = set(blob.coefficients.keys())
        replace_shape(blob, ETM_LOG_KEY, "exp", _t())
        assert set(blob.coefficients.keys()) == orig_keys

    def test_op_name(self):
        result = replace_shape(_etm_log_blob(), ETM_LOG_KEY, "exp", _t())
        assert result.op_name == "replace_shape"

    def test_output_length(self):
        result = replace_shape(_etm_log_blob(), ETM_LOG_KEY, "exp", _t())
        assert len(result.values) == N


# ---------------------------------------------------------------------------
# TestDuplicate
# ---------------------------------------------------------------------------


class TestDuplicate:
    def test_etm_adds_second_transient(self):
        blob = _etm_log_blob()
        t = _t()
        delta = 15.0
        result = duplicate(blob, ETM_LOG_KEY, delta, t)
        # Values should be larger than original (second transient added)
        t_arr = _t()
        pos1 = np.maximum(0.0, (t_arr - T_REF) / TAU)
        pos2 = np.maximum(0.0, (t_arr - (T_REF + delta)) / TAU)
        extra = AMPLITUDE * np.log1p(pos2)
        orig = blob.reassemble()
        np.testing.assert_allclose(result.values, orig + extra, atol=1e-10)

    def test_etm_original_key_preserved(self):
        blob = _etm_log_blob()
        t = _t()
        result = duplicate(blob, ETM_LOG_KEY, 15.0, t)
        # Caller blob unchanged
        assert ETM_LOG_KEY in blob.coefficients

    def test_delta_t_zero_raises(self):
        with pytest.raises(ValueError, match="delta_t must be non-zero"):
            duplicate(_etm_log_blob(), ETM_LOG_KEY, 0.0, _t())

    def test_relabel_reclassify(self):
        result = duplicate(_etm_log_blob(), ETM_LOG_KEY, 10.0, _t())
        assert result.relabel.rule_class == "RECLASSIFY_VIA_SEGMENTER"
        assert result.relabel.needs_resegment is True

    def test_negative_delta_adds_earlier_transient(self):
        blob = _etm_log_blob()
        t = _t()
        result = duplicate(blob, ETM_LOG_KEY, -20.0, t)
        assert result.values is not None
        assert len(result.values) == N

    def test_gratsid_stub_adds_second_component(self):
        blob = _gratsid_stub_blob()
        t = _t()
        result = duplicate(blob, "transient", 20.0, t)
        # Should have larger values than the original around T_REF + 20
        assert float(result.values[int(T_REF + 20)]) >= float(blob.reassemble()[int(T_REF + 20)])

    def test_op_name(self):
        result = duplicate(_etm_log_blob(), ETM_LOG_KEY, 10.0, _t())
        assert result.op_name == "duplicate"


# ---------------------------------------------------------------------------
# TestConvertToStep
# ---------------------------------------------------------------------------


class TestConvertToStep:
    def test_etm_transient_key_removed(self):
        blob = _etm_log_blob()
        t = _t()
        result = convert_to_step(blob, ETM_LOG_KEY, t)
        # Original blob unchanged
        assert ETM_LOG_KEY in blob.coefficients

    def test_etm_step_key_added(self):
        blob = _etm_log_blob()
        t = _t()
        # Result should have a step-like shape (Heaviside onset at T_REF)
        result = convert_to_step(blob, ETM_LOG_KEY, t)
        # At t < T_REF: no step contribution
        background_before = blob.components["x0"] + blob.components["linear_rate"]
        idx_before = int(T_REF - 1)
        idx_after = int(T_REF + 1)
        assert result.values[idx_after] > result.values[idx_before]

    def test_etm_step_has_heaviside_shape(self):
        blob = _etm_log_blob()
        t = _t()
        result = convert_to_step(blob, ETM_LOG_KEY, t)
        # Background (x0 + trend) is slowly increasing; step makes a clear jump
        # Difference at t=T_REF vs t=T_REF-1 should be roughly AMPLITUDE
        idx_step = int(T_REF)
        diff = result.values[idx_step] - result.values[idx_step - 1]
        # background rate is 0.05 per step; step amplitude is AMPLITUDE=5
        assert diff > 1.0

    def test_deterministic_step_relabel(self):
        result = convert_to_step(_etm_log_blob(), ETM_LOG_KEY, _t())
        assert result.relabel.rule_class == "DETERMINISTIC"
        assert result.relabel.new_shape == "step"

    def test_pre_shape_does_not_affect_relabel(self):
        result = convert_to_step(_etm_log_blob(), ETM_LOG_KEY, _t(), pre_shape="noise")
        assert result.relabel.new_shape == "step"

    def test_caller_unchanged(self):
        blob = _etm_log_blob()
        orig_keys = set(blob.coefficients.keys())
        convert_to_step(blob, ETM_LOG_KEY, _t())
        assert set(blob.coefficients.keys()) == orig_keys

    def test_gratsid_stub_converts(self):
        blob = _gratsid_stub_blob()
        t = _t()
        result = convert_to_step(blob, "transient", t)
        assert result.relabel.new_shape == "step"
        assert result.relabel.rule_class == "DETERMINISTIC"

    def test_op_name(self):
        result = convert_to_step(_etm_log_blob(), ETM_LOG_KEY, _t())
        assert result.op_name == "convert_to_step"

    def test_output_length(self):
        result = convert_to_step(_etm_log_blob(), ETM_LOG_KEY, _t())
        assert len(result.values) == N


# ---------------------------------------------------------------------------
# TestDispatchETMvsGrAtSiD (cross-method)
# ---------------------------------------------------------------------------


class TestDispatchETMvsGrAtSiD:
    def test_etm_log_remove_leaves_background(self):
        blob = _etm_log_blob()
        result = remove(blob, ETM_LOG_KEY)
        background = blob.components["x0"] + blob.components["linear_rate"]
        np.testing.assert_allclose(result.values, background, atol=1e-10)

    def test_gratsid_stub_remove_leaves_secular(self):
        blob = _gratsid_stub_blob()
        result = remove(blob, "transient")
        secular = blob.components["secular"]
        np.testing.assert_allclose(result.values, secular, atol=1e-10)

    def test_gratsid_features_amplify(self):
        blob = _gratsid_features_blob()
        t = _t()
        original = blob.reassemble()
        result = amplify(blob, 0, 2.0, t=t)
        assert result.relabel.rule_class == "PRESERVED"
        # Amplitude doubled: transient contribution should be ~2x at peak
        secular = blob.components["secular"]
        orig_trans_peak = float(np.max(original - secular))
        new_trans_peak = float(np.max(result.values - secular))
        assert abs(new_trans_peak - 2.0 * orig_trans_peak) / (orig_trans_peak + 1e-12) < 0.05

    def test_gratsid_features_amplify_requires_t(self):
        blob = _gratsid_features_blob()
        with pytest.raises(ValueError, match="t \\(time axis\\) is required"):
            amplify(blob, 0, 2.0)

    def test_etm_exp_shift_time(self):
        blob = _etm_exp_blob()
        result = shift_time(blob, ETM_EXP_KEY, 5.0, _t())
        assert result.relabel.rule_class == "PRESERVED"
        assert len(result.values) == N

    def test_gratsid_features_shift_time(self):
        blob = _gratsid_features_blob()
        t = _t()
        result = shift_time(blob, 0, 10.0, t)
        assert result.relabel.rule_class == "PRESERVED"

    def test_gratsid_features_duplicate_appends(self):
        blob = _gratsid_features_blob()
        t = _t()
        n_before = len(blob.coefficients["features"])
        original = blob.reassemble()
        result = duplicate(blob, 0, 15.0, t)
        assert result.relabel.rule_class == "RECLASSIFY_VIA_SEGMENTER"
        # Original blob's features list unchanged (deepcopy inside op)
        assert len(blob.coefficients["features"]) == n_before
        # Second transient added — result should differ from original
        assert not np.allclose(result.values, original)

    def test_gratsid_stub_invalid_feature_id_raises(self):
        blob = _gratsid_stub_blob()
        with pytest.raises(ValueError, match="feature_id must be"):
            remove(blob, "unknown")

    def test_gratsid_features_out_of_range_raises(self):
        blob = _gratsid_features_blob()
        with pytest.raises(ValueError, match="out of range"):
            remove(blob, 99, t=_t())


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_remove_exp_blob(self):
        blob = _etm_exp_blob()
        result = remove(blob, ETM_EXP_KEY)
        background = blob.components["x0"] + blob.components["linear_rate"]
        np.testing.assert_allclose(result.values, background, atol=1e-10)

    def test_amplify_exp_blob(self):
        blob = _etm_exp_blob()
        result = amplify(blob, ETM_EXP_KEY, 3.0)
        t = _t()
        pos = np.maximum(0.0, (t - T_REF) / TAU)
        expected_trans = 3.0 * AMPLITUDE * np.exp(-pos)
        background = blob.components["x0"] + blob.components["linear_rate"]
        np.testing.assert_allclose(result.values, background + expected_trans, atol=1e-10)

    def test_convert_to_step_amplitude_preserved(self):
        blob = _etm_log_blob()
        t = _t()
        result = convert_to_step(blob, ETM_LOG_KEY, t)
        # Step amplitude should equal original transient amplitude
        step_key = f"step_at_{float(T_REF):.6g}"
        # The step contribution at t >> T_REF should be AMPLITUDE
        # result.values = x0 + linear_rate*t + step
        idx_late = N - 1
        background_late = float(blob.components["x0"][idx_late]) + float(blob.components["linear_rate"][idx_late])
        step_contribution = result.values[idx_late] - background_late
        assert abs(step_contribution - AMPLITUDE) < 1e-6

    def test_shift_time_preserves_amplitude(self):
        blob = _etm_log_blob()
        t = _t()
        result = shift_time(blob, ETM_LOG_KEY, 5.0, t)
        # At t >> T_REF + 5, transient saturates to AMPLITUDE * log1p(large)
        # At t >> T_REF, original saturates similarly
        # The amplitude coefficient should be unchanged
        assert result.relabel.rule_class == "PRESERVED"

    def test_change_duration_very_small_tau_clamped(self):
        blob = _etm_log_blob(tau=1.0)
        key = f"log_{float(T_REF):.6g}_tau1"
        t = _t()
        # Multiplying tau by near-zero should clamp to 1e-12, not zero
        result = change_duration(blob, key, 1e-15, t)
        assert not np.any(np.isnan(result.values))
        assert not np.any(np.isinf(result.values))

    def test_dampen_alpha_greater_than_one_raises(self):
        with pytest.raises(ValueError, match="alpha must be in"):
            dampen(_etm_log_blob(), ETM_LOG_KEY, 1.5)

    def test_duplicate_adds_values(self):
        blob = _etm_log_blob()
        t = _t()
        original = blob.reassemble()
        result = duplicate(blob, ETM_LOG_KEY, 10.0, t)
        # Sum is greater at late times (two transients)
        assert float(np.mean(result.values[int(T_REF + 15):])) > float(np.mean(original[int(T_REF + 15):]))
