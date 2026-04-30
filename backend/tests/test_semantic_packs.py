"""Tests for the hydrology semantic pack — SEG-021.

References
----------
Eckhardt (2005), Tallaksen (1995), Wolter & Timlin (2011), Mantua & Hare (2002).
"""
from __future__ import annotations

import pathlib

import numpy as np
import pytest

from app.services import semantic_packs as sp
from app.services.semantic_packs import (
    DETECTOR_REGISTRY,
    SemanticLabel,
    SemanticPack,
    evaluate_predicate,
    label_segment,
    load_pack,
    match_semantic_label,
    register_detector,
)
from app.services.semantic_packs.core import VALID_SHAPES


RNG = np.random.default_rng(42)


# ---------------------------------------------------------------------------
# Pack loading
# ---------------------------------------------------------------------------


def test_hydrology_pack_loads():
    pack = load_pack("hydrology")
    assert isinstance(pack, SemanticPack)
    assert pack.name == "hydrology"
    assert pack.version == "1.0"
    assert isinstance(pack.semantic_labels, dict)
    assert pack.semantic_labels


def test_hydrology_pack_contains_all_nine_labels():
    pack = load_pack("hydrology")
    expected = {
        "baseflow", "stormflow", "peak_flow",
        "rising_limb", "recession_limb",
        "snowmelt_freshet", "drought",
        "ENSO_phase", "PDO_phase",
    }
    assert set(pack.semantic_labels.keys()) == expected


def test_every_label_maps_to_valid_shape():
    pack = load_pack("hydrology")
    for label in pack.semantic_labels.values():
        assert label.shape_primitive in VALID_SHAPES, (
            f"label {label.name!r} maps to unknown shape {label.shape_primitive!r}"
        )


def test_every_named_detector_resolves():
    pack = load_pack("hydrology")
    for label in pack.semantic_labels.values():
        assert label.detector_name in DETECTOR_REGISTRY, (
            f"label {label.name!r} references unregistered detector "
            f"{label.detector_name!r}"
        )


def test_load_pack_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_pack("nonexistent")


def test_load_pack_unknown_shape_raises(tmp_path: pathlib.Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "name: bad\nversion: '1.0'\nsemantic_labels:\n"
        "  oops:\n    shape_primitive: not_a_shape\n    detector: eckhardt_baseflow\n"
    )
    with pytest.raises(ValueError, match="unknown shape_primitive"):
        load_pack("bad", pack_dir=tmp_path)


def test_load_pack_unknown_detector_raises(tmp_path: pathlib.Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "name: bad\nversion: '1.0'\nsemantic_labels:\n"
        "  oops:\n    shape_primitive: plateau\n    detector: not_registered\n"
    )
    with pytest.raises(ValueError, match="unknown detector"):
        load_pack("bad", pack_dir=tmp_path)


def test_load_pack_pack_dir_override(tmp_path: pathlib.Path):
    """Loader must honour an explicit ``pack_dir`` so callers can ship
    user-defined packs separately from the bundled ones."""
    custom = tmp_path / "demo.yaml"
    custom.write_text(
        "name: demo\nversion: '0.1'\nsemantic_labels:\n"
        "  flat:\n    shape_primitive: plateau\n    detector: eckhardt_baseflow\n"
    )
    pack = load_pack("demo", pack_dir=tmp_path)
    assert pack.name == "demo"
    assert "flat" in pack.semantic_labels


# ---------------------------------------------------------------------------
# Detector signature contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "detector_name",
    sorted(DETECTOR_REGISTRY.keys()),
)
def test_every_detector_returns_bool_float_tuple(detector_name: str):
    """Detector must return ``(bool, float)`` regardless of input."""
    detector = DETECTOR_REGISTRY[detector_name]
    X = np.full(64, 5.0, dtype=np.float64)
    result = detector(X, "plateau", {"Q_median": 5.0})
    assert isinstance(result, tuple) and len(result) == 2
    matched, conf = result
    assert isinstance(matched, bool)
    assert isinstance(conf, float)
    assert 0.0 <= conf <= 1.0 or matched is False  # confidence in [0,1] when matched


def test_detector_returns_no_match_for_wrong_shape():
    """A baseflow detector run on a 'cycle' segment must reject by shape."""
    X = np.full(50, 2.0)
    matched, conf = DETECTOR_REGISTRY["eckhardt_baseflow"](X, "cycle", {})
    assert matched is False
    assert conf == 0.0


def test_register_detector_decorator_adds_to_registry():
    @register_detector("__test_detector_temp__")
    def _detector(X, shape, ctx):
        return True, 0.5

    try:
        assert "__test_detector_temp__" in DETECTOR_REGISTRY
        assert DETECTOR_REGISTRY["__test_detector_temp__"] is _detector
    finally:
        del DETECTOR_REGISTRY["__test_detector_temp__"]


# ---------------------------------------------------------------------------
# Predicate evaluator
# ---------------------------------------------------------------------------


def test_predicate_simple_comparison():
    assert evaluate_predicate("a < b", {"a": 1, "b": 2}) is True
    assert evaluate_predicate("a < b", {"a": 3, "b": 2}) is False


def test_predicate_compound_boolean():
    ctx = {"x": 5, "y": 10, "z": True}
    assert evaluate_predicate("x < y and z", ctx) is True
    assert evaluate_predicate("x > y or not z", ctx) is False


def test_predicate_arithmetic():
    assert evaluate_predicate("a * b > 6", {"a": 2, "b": 4}) is True


def test_predicate_calls_to_whitelisted_builtins():
    assert evaluate_predicate("abs(x) < 1", {"x": 0.5}) is True
    assert evaluate_predicate("max(x, y) == 7", {"x": 7, "y": 3}) is True


def test_predicate_empty_returns_true():
    assert evaluate_predicate("", {}) is True
    assert evaluate_predicate("   ", {}) is True


def test_predicate_rejects_disallowed_call(tmp_path):
    """Calls to functions outside the whitelist must be rejected before eval."""
    with pytest.raises(ValueError, match="disallowed"):
        evaluate_predicate("__import__('os')", {})


def test_predicate_rejects_attribute_access():
    """Attribute access is unsafe (e.g. ``ctx.__class__``) and rejected."""
    with pytest.raises(ValueError):
        evaluate_predicate("x.real > 0", {"x": 1+2j})


def test_predicate_rejects_lambda():
    with pytest.raises((ValueError, SyntaxError)):
        evaluate_predicate("(lambda: 1)()", {})


def test_predicate_unknown_name_raises_name_error():
    with pytest.raises(NameError):
        evaluate_predicate("x > 0", {})


def test_predicate_membership_operator():
    assert evaluate_predicate("p in [1, 2, 3]", {"p": 2}) is True
    assert evaluate_predicate("p not in [1, 2, 3]", {"p": 4}) is True


# ---------------------------------------------------------------------------
# match_semantic_label — single-label pipeline
# ---------------------------------------------------------------------------


def test_match_returns_no_match_when_shape_mismatches():
    pack = load_pack("hydrology")
    label = pack.semantic_labels["baseflow"]
    matched, _ = match_semantic_label(
        label, np.full(50, 2.0), shape_label="cycle", context={}
    )
    assert matched is False


def test_match_baseflow_on_low_constant_plateau():
    pack = load_pack("hydrology")
    label = pack.semantic_labels["baseflow"]
    Q = np.full(120, 2.0, dtype=np.float64)
    context = {"Q_median": 10.0}
    matched, conf = match_semantic_label(label, Q, "plateau", context=context)
    assert matched is True
    assert conf > 0.0


def test_match_baseflow_rejects_high_plateau():
    pack = load_pack("hydrology")
    label = pack.semantic_labels["baseflow"]
    Q = np.full(120, 12.0, dtype=np.float64)
    context = {"Q_median": 5.0}
    matched, _ = match_semantic_label(label, Q, "plateau", context=context)
    assert matched is False


def test_match_drought_on_extended_low_flow():
    pack = load_pack("hydrology")
    label = pack.semantic_labels["drought"]
    Q = np.full(60, 0.05, dtype=np.float64)
    context = {"Q_median": 1.0, "samples_per_day": 1.0}
    matched, conf = match_semantic_label(label, Q, "plateau", context=context)
    assert matched is True
    assert conf > 0.0


def test_match_peak_flow_on_short_outlier_spike():
    pack = load_pack("hydrology")
    label = pack.semantic_labels["peak_flow"]
    Q = np.array([1.0, 1.1, 0.9, 1.0, 12.0, 1.0, 0.95, 1.05])
    context = {"Q_median": 1.0, "dt": 1.0}
    matched, _ = match_semantic_label(label, Q, "spike", context=context)
    assert matched is True


def test_match_rising_limb_requires_preceded_by_baseflow():
    pack = load_pack("hydrology")
    label = pack.semantic_labels["rising_limb"]
    Q = np.linspace(1.0, 5.0, 20)
    no_neighbour, _ = match_semantic_label(label, Q, "trend", context={})
    with_neighbour, _ = match_semantic_label(
        label, Q, "trend", context={"preceded_by_baseflow": True}
    )
    assert no_neighbour is False
    assert with_neighbour is True


def test_match_recession_limb_requires_follows_peak_flow_and_negative_slope():
    pack = load_pack("hydrology")
    label = pack.semantic_labels["recession_limb"]
    Q = np.linspace(5.0, 1.0, 60)  # gentle decline
    matched, _ = match_semantic_label(
        label, Q, "trend", context={"follows_peak_flow": True}
    )
    assert matched is True


def test_match_recession_limb_rejects_steep_slope_above_max():
    pack = load_pack("hydrology")
    label = pack.semantic_labels["recession_limb"]
    Q = np.linspace(20.0, 1.0, 5)  # very steep
    matched, _ = match_semantic_label(
        label, Q, "trend", context={"follows_peak_flow": True}
    )
    assert matched is False


def test_match_enso_period_in_band():
    pack = load_pack("hydrology")
    label = pack.semantic_labels["ENSO_phase"]
    samples_per_year = 12
    period_years = 4
    n = period_years * samples_per_year * 4  # 4 cycles for clarity
    t = np.arange(n)
    X = np.sin(2 * np.pi * t / (period_years * samples_per_year))
    matched, conf = match_semantic_label(
        label, X, "cycle", context={"samples_per_year": samples_per_year}
    )
    assert matched is True
    assert conf == 1.0


def test_match_pdo_period_outside_band_rejected_for_short_period():
    pack = load_pack("hydrology")
    label = pack.semantic_labels["PDO_phase"]
    samples_per_year = 12
    period_years = 4  # too short for PDO band [15,30]
    n = 360
    t = np.arange(n)
    X = np.sin(2 * np.pi * t / (period_years * samples_per_year))
    matched, _ = match_semantic_label(
        label, X, "cycle", context={"samples_per_year": samples_per_year}
    )
    assert matched is False


def test_match_pdo_period_inside_band():
    pack = load_pack("hydrology")
    label = pack.semantic_labels["PDO_phase"]
    samples_per_year = 12
    period_years = 20
    n = period_years * samples_per_year * 3
    t = np.arange(n)
    X = np.sin(2 * np.pi * t / (period_years * samples_per_year))
    matched, _ = match_semantic_label(
        label, X, "cycle", context={"samples_per_year": samples_per_year}
    )
    assert matched is True


# ---------------------------------------------------------------------------
# Integration — synthetic hydrograph with known segments
# ---------------------------------------------------------------------------


def test_hydrograph_fixture_attaches_expected_labels():
    """Build a hydrograph with three known segments — baseflow plateau,
    stormflow transient, and a recession limb — then label each via
    :func:`label_segment` and confirm the canonical label is the top match."""
    pack = load_pack("hydrology")
    Q_median = 5.0

    # Baseflow segment: long, flat, well below Q_median.
    Q_baseflow = np.full(60, 1.0, dtype=np.float64)
    labels_b = label_segment(
        pack, Q_baseflow, "plateau", context={"Q_median": Q_median}
    )
    assert any(name == "baseflow" for name, _ in labels_b), (
        f"expected 'baseflow' label, got {labels_b}"
    )

    # Stormflow transient: rising limb with a peak well above 3× median.
    Q_storm = np.concatenate([
        np.linspace(2.0, 25.0, 8),
        np.linspace(25.0, 6.0, 12),
    ])
    labels_s = label_segment(
        pack, Q_storm, "transient", context={"Q_median": Q_median}
    )
    assert any(name == "stormflow" for name, _ in labels_s), (
        f"expected 'stormflow' label, got {labels_s}"
    )

    # Recession limb: gentle declining trend following a peak.
    Q_recession = np.linspace(8.0, 2.0, 80)
    labels_r = label_segment(
        pack, Q_recession, "trend",
        context={"Q_median": Q_median, "follows_peak_flow": True},
    )
    assert any(name == "recession_limb" for name, _ in labels_r), (
        f"expected 'recession_limb' label, got {labels_r}"
    )


def test_label_segment_returns_descending_confidence():
    """When multiple labels match, the result list is sorted by confidence."""
    pack = load_pack("hydrology")

    # Single segment that satisfies both 'baseflow' and 'drought' (low flat
    # plateau over many samples).
    Q = np.full(100, 0.05, dtype=np.float64)
    labels = label_segment(
        pack, Q, "plateau",
        context={"Q_median": 1.0, "samples_per_day": 1.0},
    )
    confidences = [c for _, c in labels]
    assert confidences == sorted(confidences, reverse=True)


def test_label_segment_returns_empty_for_unmatched_segment():
    """A noisy segment of the wrong shape should produce no labels."""
    pack = load_pack("hydrology")
    Q = RNG.normal(size=200)
    labels = label_segment(pack, Q, "noise", context={"Q_median": 1.0})
    assert labels == []


# ---------------------------------------------------------------------------
# User-defined-label shadowing contract (documented in load_pack)
# ---------------------------------------------------------------------------


def test_user_defined_labels_can_shadow_pack_labels():
    """Per Implementation Plan §8.4, callers shadow pack labels by replacing
    entries in the dict before use — verify the dict semantics support this."""
    pack = load_pack("hydrology")
    user_labels = dict(pack.semantic_labels)
    user_labels["baseflow"] = SemanticLabel(
        name="baseflow",
        shape_primitive="plateau",
        detector_name="eckhardt_baseflow",
        detector_params={"BFImax": 0.95, "a": 0.99},  # user override
    )
    assert user_labels["baseflow"].detector_params["BFImax"] == 0.95
    # Original pack instance must remain unmodified (frozen dataclass)
    assert pack.semantic_labels["baseflow"].detector_params["BFImax"] == 0.8


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_module_exports_public_surface():
    for name in (
        "DETECTOR_REGISTRY", "SemanticLabel", "SemanticPack",
        "evaluate_predicate", "label_segment", "load_pack",
        "match_semantic_label", "register_detector",
    ):
        assert hasattr(sp, name), f"app.services.semantic_packs missing {name}"
