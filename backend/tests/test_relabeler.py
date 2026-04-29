"""Tests for OP-040: relabeler rule table (3 classes, ≥48 entries).

Covers:
 - Every (old_shape, operation) pair in RULE_TABLE → expected rule class
 - DETERMINISTIC entries return correct target shape
 - alpha=0 param predicate dispatch
 - Wildcard (*) shape for Tier-0 and Tier-1 ops
 - RECLASSIFY_VIA_SEGMENTER path invokes SEG-008 classifier
 - RECLASSIFY without edited_series returns confidence-0 stub
 - Unknown (old_shape, operation) raises UnknownRelabelRule
 - _param_predicate extracts 'alpha=0' or None
"""

import numpy as np
import pytest

from app.services.operations.relabeler.relabeler import RelabelResult, relabel
from app.services.operations.relabeler.rule_table import (
    RULE_TABLE,
    UnknownRelabelRule,
    _param_predicate,
)


# ---------------------------------------------------------------------------
# _param_predicate
# ---------------------------------------------------------------------------


class TestParamPredicate:
    def test_none_params(self):
        assert _param_predicate(None) is None

    def test_empty_dict(self):
        assert _param_predicate({}) is None

    def test_alpha_zero_float(self):
        assert _param_predicate({"alpha": 0.0}) == "alpha=0"

    def test_alpha_zero_int(self):
        assert _param_predicate({"alpha": 0}) == "alpha=0"

    def test_alpha_nonzero(self):
        assert _param_predicate({"alpha": 0.5}) is None

    def test_alpha_negative(self):
        assert _param_predicate({"alpha": -1.0}) is None

    def test_other_params_no_alpha(self):
        assert _param_predicate({"weight": 0.1, "seed": 42}) is None

    def test_alpha_zero_among_other_params(self):
        assert _param_predicate({"alpha": 0.0, "other": 99}) == "alpha=0"


# ---------------------------------------------------------------------------
# Rule table coverage: count
# ---------------------------------------------------------------------------


def test_rule_table_has_at_least_48_entries():
    assert len(RULE_TABLE) >= 48


# ---------------------------------------------------------------------------
# PRESERVED entries
# ---------------------------------------------------------------------------

_PRESERVED_CASES = [
    # Tier-0
    ("trend", "edit_boundary"),
    ("cycle", "edit_boundary"),
    # Tier-1 amplitude
    ("trend", "scale"),          # via wildcard + None predicate (alpha != 0)
    ("plateau", "offset"),
    ("noise", "add_uncertainty"),
    # Tier-1 time
    ("trend", "time_shift"),
    ("cycle", "reverse_time"),
    ("step", "resample"),
    # Tier-2 plateau
    ("plateau", "raise_lower"),
    ("plateau", "invert"),
    ("plateau", "tilt_detrend"),
    # Tier-2 trend
    ("trend", "reverse_direction"),
    ("trend", "change_slope"),   # alpha != 0
    ("trend", "linearise"),
    ("trend", "extrapolate"),
    ("trend", "add_acceleration"),
    # Tier-2 step
    ("step", "invert_sign"),
    ("step", "scale_magnitude"),  # alpha != 0
    ("step", "shift_in_time"),
    # Tier-2 spike
    ("spike", "clip_cap"),
    ("spike", "amplify"),
    ("spike", "shift_time"),
    # Tier-2 cycle
    ("cycle", "amplify_amplitude"),  # alpha != 0
    ("cycle", "dampen_amplitude"),
    ("cycle", "phase_shift"),
    ("cycle", "change_period"),
    ("cycle", "change_harmonic_content"),
    # Tier-2 transient
    ("transient", "amplify"),
    ("transient", "dampen"),          # alpha != 0
    ("transient", "shift_time"),
    ("transient", "change_duration"),
    ("transient", "change_decay_constant"),
    ("transient", "replace_shape"),
    ("transient", "duplicate"),
    # Tier-2 noise
    ("noise", "amplify"),
    ("noise", "change_color"),
    ("noise", "inject_synthetic"),
    ("noise", "whiten"),
]


@pytest.mark.parametrize("old_shape,operation", _PRESERVED_CASES)
def test_preserved_returns_old_shape(old_shape, operation):
    result = relabel(old_shape, operation)
    assert result.rule_class == "PRESERVED"
    assert result.new_shape == old_shape
    assert result.confidence == 1.0
    assert result.needs_resegment is False


# ---------------------------------------------------------------------------
# DETERMINISTIC entries
# ---------------------------------------------------------------------------

_DETERMINISTIC_CASES = [
    # (old_shape, operation, op_params, expected_target)
    ("*",         "scale",             {"alpha": 0.0}, "plateau"),
    ("*",         "mute_zero",         None,           "plateau"),
    ("plateau",   "replace_with_trend",None,           "trend"),
    ("plateau",   "replace_with_cycle",None,           "cycle"),
    ("trend",     "flatten",           None,           "plateau"),
    ("trend",     "change_slope",      {"alpha": 0.0}, "plateau"),
    ("step",      "scale_magnitude",   {"alpha": 0.0}, "plateau"),
    ("step",      "convert_to_ramp",   None,           "transient"),
    ("spike",     "smear_to_transient",None,           "transient"),
    ("cycle",     "amplify_amplitude", {"alpha": 0.0}, "plateau"),
    ("cycle",     "replace_with_flat", None,           "plateau"),
    ("transient", "dampen",            {"alpha": 0.0}, "plateau"),
    ("transient", "convert_to_step",   None,           "step"),
]


@pytest.mark.parametrize("old_shape,operation,op_params,expected_target", _DETERMINISTIC_CASES)
def test_deterministic_returns_target(old_shape, operation, op_params, expected_target):
    result = relabel(old_shape, operation, op_params=op_params)
    assert result.rule_class == "DETERMINISTIC"
    assert result.new_shape == expected_target
    assert result.confidence == 1.0
    assert result.needs_resegment is False


# ---------------------------------------------------------------------------
# RECLASSIFY_VIA_SEGMENTER entries (no edited_series — stub path)
# ---------------------------------------------------------------------------

_RECLASSIFY_CASES = [
    ("*",        "split"),
    ("*",        "merge"),
    ("*",        "suppress"),
    ("*",        "replace_from_library"),
    ("step",     "de_jump"),
    ("step",     "duplicate"),
    ("spike",    "remove"),
    ("spike",    "duplicate"),
    ("cycle",    "deseasonalise_remove"),
    ("transient","remove"),
    ("noise",    "suppress_denoise"),
]


@pytest.mark.parametrize("old_shape,operation", _RECLASSIFY_CASES)
def test_reclassify_stub_without_series(old_shape, operation):
    """Without edited_series, returns confidence-0 stub."""
    result = relabel(old_shape, operation, edited_series=None)
    assert result.rule_class == "RECLASSIFY_VIA_SEGMENTER"
    assert result.needs_resegment is True
    assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# RECLASSIFY_VIA_SEGMENTER — classifier invoked with edited_series
# ---------------------------------------------------------------------------


class TestReclassifyWithSeries:
    def test_merge_invokes_classifier(self):
        """merge with a flat edited_series → classifier returns a shape."""
        flat = np.ones(50)
        result = relabel("plateau", "merge", edited_series=flat)
        assert result.rule_class == "RECLASSIFY_VIA_SEGMENTER"
        assert result.needs_resegment is True
        assert result.new_shape in {
            "plateau", "trend", "step", "spike", "cycle", "transient", "noise"
        }
        assert 0.0 <= result.confidence <= 1.0

    def test_split_invokes_classifier(self):
        """split with a trending series → classifier returns a shape."""
        trending = np.linspace(0, 10, 80)
        result = relabel("trend", "split", edited_series=trending)
        assert result.rule_class == "RECLASSIFY_VIA_SEGMENTER"
        assert result.new_shape in {
            "plateau", "trend", "step", "spike", "cycle", "transient", "noise"
        }

    def test_reclassify_accepts_custom_classifier(self):
        """Custom classifier result is forwarded through RelabelResult."""
        from unittest.mock import MagicMock
        from app.services.suggestion.rule_classifier import ShapeLabel

        mock_clf = MagicMock()
        mock_clf.classify_shape.return_value = ShapeLabel(
            label="trend", confidence=0.9, per_class_scores={}
        )
        result = relabel(
            "noise", "suppress_denoise",
            edited_series=np.linspace(0, 1, 30),
            classifier=mock_clf,
        )
        assert result.new_shape == "trend"
        assert result.confidence == pytest.approx(0.9)
        mock_clf.classify_shape.assert_called_once()

    def test_suppress_denoise_reclassify(self):
        result = relabel("noise", "suppress_denoise", edited_series=np.ones(40))
        assert result.rule_class == "RECLASSIFY_VIA_SEGMENTER"


# ---------------------------------------------------------------------------
# Alpha=0 predicate dispatch
# ---------------------------------------------------------------------------


class TestAlphaZeroPredicate:
    def test_change_slope_alpha_zero_is_deterministic_plateau(self):
        result = relabel("trend", "change_slope", op_params={"alpha": 0.0})
        assert result.rule_class == "DETERMINISTIC"
        assert result.new_shape == "plateau"

    def test_change_slope_alpha_nonzero_is_preserved(self):
        result = relabel("trend", "change_slope", op_params={"alpha": 0.5})
        assert result.rule_class == "PRESERVED"
        assert result.new_shape == "trend"

    def test_scale_alpha_zero_is_plateau(self):
        result = relabel("cycle", "scale", op_params={"alpha": 0.0})
        assert result.rule_class == "DETERMINISTIC"
        assert result.new_shape == "plateau"

    def test_scale_alpha_one_is_preserved(self):
        result = relabel("cycle", "scale", op_params={"alpha": 1.0})
        assert result.rule_class == "PRESERVED"

    def test_amplify_amplitude_alpha_zero_is_plateau(self):
        result = relabel("cycle", "amplify_amplitude", op_params={"alpha": 0.0})
        assert result.rule_class == "DETERMINISTIC"
        assert result.new_shape == "plateau"

    def test_scale_magnitude_alpha_zero_is_plateau(self):
        result = relabel("step", "scale_magnitude", op_params={"alpha": 0.0})
        assert result.rule_class == "DETERMINISTIC"
        assert result.new_shape == "plateau"

    def test_dampen_alpha_zero_is_plateau(self):
        result = relabel("transient", "dampen", op_params={"alpha": 0.0})
        assert result.rule_class == "DETERMINISTIC"
        assert result.new_shape == "plateau"

    def test_dampen_alpha_half_is_preserved(self):
        result = relabel("transient", "dampen", op_params={"alpha": 0.5})
        assert result.rule_class == "PRESERVED"


# ---------------------------------------------------------------------------
# Wildcard shape dispatch
# ---------------------------------------------------------------------------


class TestWildcardShape:
    def test_edit_boundary_any_shape(self):
        for shape in ("plateau", "trend", "step", "spike", "cycle", "transient", "noise"):
            result = relabel(shape, "edit_boundary")
            assert result.rule_class == "PRESERVED"
            assert result.new_shape == shape

    def test_merge_any_shape(self):
        for shape in ("plateau", "trend", "step"):
            result = relabel(shape, "merge", edited_series=None)
            assert result.rule_class == "RECLASSIFY_VIA_SEGMENTER"

    def test_time_shift_any_shape(self):
        for shape in ("plateau", "trend", "cycle", "noise"):
            result = relabel(shape, "time_shift")
            assert result.rule_class == "PRESERVED"
            assert result.new_shape == shape

    def test_replace_from_library_any_shape(self):
        result = relabel("trend", "replace_from_library", edited_series=None)
        assert result.rule_class == "RECLASSIFY_VIA_SEGMENTER"


# ---------------------------------------------------------------------------
# Unknown rule raises
# ---------------------------------------------------------------------------


class TestUnknownRule:
    def test_unknown_operation_raises(self):
        with pytest.raises(UnknownRelabelRule, match="No relabel rule"):
            relabel("plateau", "nonexistent_op")

    def test_unknown_shape_raises(self):
        with pytest.raises(UnknownRelabelRule):
            relabel("ghost_shape", "flatten")

    def test_shape_op_mismatch_raises(self):
        # 'flatten' is a trend op — should raise for 'step' shape
        with pytest.raises(UnknownRelabelRule):
            relabel("step", "flatten")

    def test_wrong_tier2_op_for_shape_raises(self):
        # 'deseasonalise_remove' is cycle-specific, not valid for plateau
        with pytest.raises(UnknownRelabelRule):
            relabel("plateau", "deseasonalise_remove")


# ---------------------------------------------------------------------------
# RelabelResult contract
# ---------------------------------------------------------------------------


class TestRelabelResultContract:
    def test_is_frozen(self):
        result = relabel("trend", "linearise")
        with pytest.raises((AttributeError, TypeError)):
            result.new_shape = "noise"  # type: ignore[misc]

    def test_fields_present(self):
        result = relabel("plateau", "raise_lower")
        assert hasattr(result, "new_shape")
        assert hasattr(result, "confidence")
        assert hasattr(result, "needs_resegment")
        assert hasattr(result, "rule_class")

    def test_confidence_in_range(self):
        for shape, op in [("trend", "flatten"), ("cycle", "phase_shift"),
                          ("step", "de_jump")]:
            kwargs = {"edited_series": np.ones(20)} if op == "de_jump" else {}
            result = relabel(shape, op, **kwargs)
            assert 0.0 <= result.confidence <= 1.0

    def test_rule_class_is_one_of_three(self):
        valid = {"PRESERVED", "DETERMINISTIC", "RECLASSIFY_VIA_SEGMENTER"}
        for (shape, op, pred), _ in RULE_TABLE.items():
            actual_shape = "trend" if shape == "*" else shape
            params = {"alpha": 0.0} if pred == "alpha=0" else None
            try:
                result = relabel(actual_shape, op, op_params=params, edited_series=None)
                assert result.rule_class in valid
            except UnknownRelabelRule:
                pass  # Some wildcard entries only work via actual shape
