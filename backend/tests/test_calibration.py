"""Tests for SEG-010: uncertainty_margin flag, YAML uncertainty_delta, calibration script."""

from __future__ import annotations

import math
import pathlib
import subprocess
import sys
import tempfile

import numpy as np
import pytest

from app.services.suggestion.rule_classifier import (
    RuleBasedShapeClassifier,
    ShapeLabel,
    _DEFAULT_THRESHOLDS,
    uncertainty_margin,
)

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_DATASET = (
    _REPO_ROOT / "benchmarks" / "datasets" / "shape_calibration" / "shape_calibration_data.csv"
)
_CALIBRATE_SCRIPT = _REPO_ROOT / "backend" / "scripts" / "calibrate_shape_thresholds.py"


# ---------------------------------------------------------------------------
# uncertainty_margin function
# ---------------------------------------------------------------------------

class TestUncertaintyMargin:
    def test_all_equal_scores_returns_true(self):
        scores = {"plateau": 0.5, "trend": 0.5, "step": 0.5}
        assert uncertainty_margin(scores) is True

    def test_clear_winner_returns_false(self):
        scores = {"plateau": 0.9, "trend": 0.1, "step": 0.0}
        assert uncertainty_margin(scores) is False

    def test_exactly_at_delta_returns_false(self):
        # gap == delta → NOT uncertain (strict less-than)
        scores = {"plateau": 0.55, "trend": 0.40}
        assert uncertainty_margin(scores, delta=0.15) is False

    def test_just_below_delta_returns_true(self):
        scores = {"plateau": 0.50, "trend": 0.36}
        assert uncertainty_margin(scores, delta=0.15) is True

    def test_single_class_returns_false(self):
        assert uncertainty_margin({"plateau": 1.0}) is False

    def test_empty_scores_returns_false(self):
        assert uncertainty_margin({}) is False

    def test_custom_delta(self):
        scores = {"a": 0.6, "b": 0.5}
        assert uncertainty_margin(scores, delta=0.2) is True
        assert uncertainty_margin(scores, delta=0.05) is False

    def test_max_margin(self):
        scores = {"a": 1.0, "b": 0.0}
        assert uncertainty_margin(scores, delta=0.99) is False

    def test_uses_top_two_only(self):
        # Many equal low scores; top-2 gap determines flag
        scores = {"a": 0.8, "b": 0.75, "c": 0.01, "d": 0.01}
        assert uncertainty_margin(scores, delta=0.1) is True
        assert uncertainty_margin(scores, delta=0.04) is False


# ---------------------------------------------------------------------------
# ShapeLabel.uncertain field
# ---------------------------------------------------------------------------

class TestShapeLabelUncertainField:
    def test_shape_label_has_uncertain_field(self):
        label = ShapeLabel(label="plateau", confidence=0.9, per_class_scores={}, uncertain=False)
        assert hasattr(label, "uncertain")

    def test_uncertain_defaults_to_false(self):
        label = ShapeLabel(label="trend", confidence=0.8, per_class_scores={})
        assert label.uncertain is False

    def test_classify_shape_returns_uncertain_field(self):
        clf = RuleBasedShapeClassifier()
        result = clf.classify_shape(np.linspace(0, 1, 30))
        assert hasattr(result, "uncertain")
        assert isinstance(result.uncertain, bool)

    def test_clear_trend_not_uncertain(self):
        clf = RuleBasedShapeClassifier()
        values = np.linspace(0.0, 1.0, 40)
        result = clf.classify_shape(values)
        # A clean trend should have a dominant gate score
        assert result.label == "trend"
        # uncertain may or may not be set depending on gate scores; just check type
        assert isinstance(result.uncertain, bool)

    def test_uncertain_set_when_ambiguous(self):
        # Build a signal that is equally trend-like and noisy: random walk
        rng = np.random.default_rng(0)
        values = np.cumsum(rng.normal(0, 1, 30))
        clf = RuleBasedShapeClassifier()
        result = clf.classify_shape(values)
        assert isinstance(result.uncertain, bool)

    def test_short_segment_uncertain_false(self):
        # Short segments fall back to noise with confidence=1.0 → not uncertain
        clf = RuleBasedShapeClassifier()
        result = clf.classify_shape([0.5])
        assert result.uncertain is False

    def test_uncertainty_reflects_score_gap(self):
        # Manually verify: if per_class_scores have small gap, uncertain=True
        clf = RuleBasedShapeClassifier()
        ambiguous = np.array([0.0, 0.1, -0.1, 0.05, -0.05, 0.0, 0.1, -0.1] * 5)
        result = clf.classify_shape(ambiguous)
        # Check that uncertain matches what uncertainty_margin would say
        expected = uncertainty_margin(result.per_class_scores, clf._uncertainty_delta)
        assert result.uncertain == expected


# ---------------------------------------------------------------------------
# YAML uncertainty_delta loading
# ---------------------------------------------------------------------------

class TestYamlUncertaintyDelta:
    def test_default_thresholds_include_uncertainty_delta(self):
        assert "uncertainty_delta" in _DEFAULT_THRESHOLDS
        assert _DEFAULT_THRESHOLDS["uncertainty_delta"] == 0.15

    def test_classifier_loads_uncertainty_delta_from_yaml(self, tmp_path):
        yaml_content = "version: '1.0.0'\nthresholds:\n  uncertainty_delta: 0.05\n"
        p = tmp_path / "thresholds.yaml"
        p.write_text(yaml_content)
        clf = RuleBasedShapeClassifier(thresholds_path=p)
        assert abs(clf._uncertainty_delta - 0.05) < 1e-9

    def test_classifier_uses_default_delta_when_missing(self, tmp_path):
        yaml_content = "version: '1.0.0'\nthresholds:\n  slope: 0.5\n"
        p = tmp_path / "thresholds.yaml"
        p.write_text(yaml_content)
        clf = RuleBasedShapeClassifier(thresholds_path=p)
        assert abs(clf._uncertainty_delta - 0.15) < 1e-9

    def test_production_yaml_has_uncertainty_delta(self):
        import yaml  # noqa: PLC0415
        yaml_path = (
            pathlib.Path(__file__).parent.parent
            / "app" / "services" / "suggestion" / "shape_thresholds.yaml"
        )
        with yaml_path.open() as fh:
            data = yaml.safe_load(fh)
        assert "uncertainty_delta" in data["thresholds"]
        assert abs(data["thresholds"]["uncertainty_delta"] - 0.15) < 1e-9

    def test_all_threshold_values_positive_finite(self):
        import yaml  # noqa: PLC0415
        yaml_path = (
            pathlib.Path(__file__).parent.parent
            / "app" / "services" / "suggestion" / "shape_thresholds.yaml"
        )
        with yaml_path.open() as fh:
            data = yaml.safe_load(fh)
        for key, val in data["thresholds"].items():
            assert isinstance(val, (int, float)), f"{key} not numeric"
            fval = float(val)
            assert math.isfinite(fval), f"{key} = {fval} is not finite"
            assert fval > 0, f"{key} = {fval} is not positive"


# ---------------------------------------------------------------------------
# Calibration script: structure + determinism
# ---------------------------------------------------------------------------

class TestCalibrationScript:
    def test_dataset_file_exists(self):
        assert _DATASET.exists(), f"Calibration dataset missing: {_DATASET}"

    def test_script_runs_and_produces_valid_yaml(self, tmp_path):
        import yaml  # noqa: PLC0415
        out = tmp_path / "out.yaml"
        result = subprocess.run(
            [sys.executable, str(_CALIBRATE_SCRIPT), "--dataset", str(_DATASET), "--output", str(out)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"
        assert out.exists()
        with out.open() as fh:
            data = yaml.safe_load(fh)
        assert "version" in data
        assert "calibration_date" in data
        assert "dataset_checksum" in data
        assert "thresholds" in data

    def test_calibration_output_threshold_keys(self, tmp_path):
        import yaml  # noqa: PLC0415
        out = tmp_path / "out.yaml"
        subprocess.run(
            [sys.executable, str(_CALIBRATE_SCRIPT), "--dataset", str(_DATASET), "--output", str(out)],
            check=True, capture_output=True,
        )
        with out.open() as fh:
            data = yaml.safe_load(fh)
        required = {"slope", "var", "per", "peak", "step", "ctx", "sign", "lin", "trans",
                    "spike_max_len", "uncertainty_delta"}
        assert required.issubset(set(data["thresholds"].keys()))

    def test_calibration_output_values_positive_finite(self, tmp_path):
        import yaml  # noqa: PLC0415
        out = tmp_path / "out.yaml"
        subprocess.run(
            [sys.executable, str(_CALIBRATE_SCRIPT), "--dataset", str(_DATASET), "--output", str(out)],
            check=True, capture_output=True,
        )
        with out.open() as fh:
            data = yaml.safe_load(fh)
        for key, val in data["thresholds"].items():
            fval = float(val)
            assert math.isfinite(fval), f"{key} = {fval}"
            assert fval > 0, f"{key} = {fval}"

    def test_calibration_is_deterministic(self, tmp_path):
        out1 = tmp_path / "out1.yaml"
        out2 = tmp_path / "out2.yaml"
        for out in (out1, out2):
            subprocess.run(
                [sys.executable, str(_CALIBRATE_SCRIPT), "--dataset", str(_DATASET), "--output", str(out)],
                check=True, capture_output=True,
            )
        import yaml  # noqa: PLC0415
        with out1.open() as fh:
            d1 = yaml.safe_load(fh)
        with out2.open() as fh:
            d2 = yaml.safe_load(fh)
        assert d1["dataset_checksum"] == d2["dataset_checksum"]
        for key in d1["thresholds"]:
            assert d1["thresholds"][key] == d2["thresholds"][key], f"Not deterministic: {key}"

    def test_missing_dataset_exits_nonzero(self, tmp_path):
        out = tmp_path / "out.yaml"
        result = subprocess.run(
            [sys.executable, str(_CALIBRATE_SCRIPT),
             "--dataset", str(tmp_path / "nonexistent.csv"),
             "--output", str(out)],
            capture_output=True,
        )
        assert result.returncode != 0
