"""Unit tests for boundary_f1 and label_accuracy in evaluation/segmentation_eval.py (SEG-006).

Imports from the evaluation package via sys.path (same pattern as
test_evaluation_harness.py — no Flask app context required).

Covers:
  - boundary_f1: perfect match, no match, partial match, tolerance window,
    empty proposed, empty true, empty both
  - label_accuracy: all correct, none correct, no IoU match (below threshold),
    partial match, empty inputs
  - derive_true_boundaries: basic change detection
  - derive_true_segments: grouping consecutive same-class runs
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "backend"))

_mod = importlib.import_module("evaluation.segmentation_eval")
boundary_f1 = _mod.boundary_f1
label_accuracy = _mod.label_accuracy
Segment = _mod.Segment
derive_true_boundaries = _mod.derive_true_boundaries
derive_true_segments = _mod.derive_true_segments


# ---------------------------------------------------------------------------
# boundary_f1
# ---------------------------------------------------------------------------


class TestBoundaryF1:
    def test_perfect_match_returns_all_ones(self):
        result = boundary_f1([10, 40, 70], [10, 40, 70], tolerance=3)
        assert result["precision"] == 1.0
        assert result["recall"] == 1.0
        assert result["f1"] == 1.0

    def test_empty_both_returns_all_ones(self):
        result = boundary_f1([], [], tolerance=3)
        assert result["f1"] == 1.0

    def test_empty_proposed_returns_zero_f1(self):
        result = boundary_f1([], [30], tolerance=3)
        assert result["f1"] == 0.0
        assert result["precision"] == 0.0  # 0 TP / max(1, 0 proposed) = 0
        assert result["recall"] == 0.0

    def test_empty_true_returns_zero_recall_zero_f1(self):
        result = boundary_f1([30], [], tolerance=3)
        assert result["recall"] == 0.0
        assert result["f1"] == 0.0

    def test_exact_hit_within_tolerance(self):
        result = boundary_f1([43], [40], tolerance=3)  # 43-40=3 ≤ 3
        assert result["precision"] == 1.0
        assert result["recall"] == 1.0
        assert result["f1"] == 1.0

    def test_just_outside_tolerance_is_miss(self):
        result = boundary_f1([44], [40], tolerance=3)  # 44-40=4 > 3
        assert result["precision"] == 0.0
        assert result["f1"] == 0.0

    def test_partial_match(self):
        result = boundary_f1([10, 50], [10, 40, 70], tolerance=3)
        # [10] matches [10], [50] misses [40] and [70]
        assert result["precision"] == 0.5
        assert round(result["recall"], 4) == round(1 / 3, 4)

    def test_f1_formula_holds(self):
        result = boundary_f1([10, 20, 50], [10, 20, 30], tolerance=3)
        p = result["precision"]
        r = result["recall"]
        if p + r > 0:
            expected_f1 = round(2 * p * r / (p + r), 6)
            assert result["f1"] == expected_f1

    def test_returns_dict_with_correct_keys(self):
        result = boundary_f1([10], [10], tolerance=3)
        assert set(result.keys()) == {"precision", "recall", "f1"}

    def test_tolerance_zero_requires_exact(self):
        result = boundary_f1([11], [10], tolerance=0)
        assert result["f1"] == 0.0
        result2 = boundary_f1([10], [10], tolerance=0)
        assert result2["f1"] == 1.0

    def test_each_true_boundary_matched_at_most_once(self):
        # Two proposed both within tolerance of the same true boundary.
        result = boundary_f1([9, 11], [10], tolerance=3)
        # Only one TP possible (one true boundary).
        assert result["recall"] == 1.0  # 1/1
        assert result["precision"] == 0.5  # 1/2


# ---------------------------------------------------------------------------
# label_accuracy
# ---------------------------------------------------------------------------


class TestLabelAccuracy:
    def _seg(self, start, end, label):
        return Segment(start, end, label)

    def test_all_correct_returns_one(self):
        proposed = [self._seg(0, 49, "trend"), self._seg(50, 99, "plateau")]
        true_segs = [self._seg(0, 49, "trend"), self._seg(50, 99, "plateau")]
        assert label_accuracy(proposed, true_segs) == 1.0

    def test_all_wrong_labels_returns_zero(self):
        proposed = [self._seg(0, 49, "spike"), self._seg(50, 99, "event")]
        true_segs = [self._seg(0, 49, "trend"), self._seg(50, 99, "plateau")]
        assert label_accuracy(proposed, true_segs) == 0.0

    def test_empty_proposed_returns_zero(self):
        true_segs = [self._seg(0, 49, "trend")]
        assert label_accuracy([], true_segs) == 0.0

    def test_empty_true_returns_zero(self):
        proposed = [self._seg(0, 49, "trend")]
        assert label_accuracy(proposed, []) == 0.0

    def test_no_iou_overlap_returns_zero(self):
        # Proposed and true cover completely different ranges.
        proposed = [self._seg(0, 49, "trend")]
        true_segs = [self._seg(50, 99, "trend")]
        assert label_accuracy(proposed, true_segs) == 0.0

    def test_iou_just_below_threshold_not_counted(self):
        # IoU = 0.5 is the threshold (>0.5 required, not >=0.5).
        # true = [0,9] len=10, proposed = [5,14] len=10, overlap=[5,9] len=5
        # IoU = 5 / (10+10-5) = 5/15 ≈ 0.333 < 0.5
        proposed = [self._seg(5, 14, "trend")]
        true_segs = [self._seg(0, 9, "trend")]
        assert label_accuracy(proposed, true_segs) == 0.0

    def test_iou_above_threshold_counted(self):
        # true = [0,9] len=10, proposed = [1,10] len=10, overlap=[1,9] len=9
        # IoU = 9 / (10+10-9) = 9/11 ≈ 0.818 > 0.5
        proposed = [self._seg(1, 10, "trend")]
        true_segs = [self._seg(0, 9, "trend")]
        assert label_accuracy(proposed, true_segs) == 1.0

    def test_partial_correct(self):
        proposed = [self._seg(0, 29, "trend"), self._seg(30, 59, "spike")]
        true_segs = [self._seg(0, 29, "trend"), self._seg(30, 59, "plateau")]
        # First pair: correct. Second pair: wrong label.
        result = label_accuracy(proposed, true_segs)
        assert result == 0.5


# ---------------------------------------------------------------------------
# derive_true_boundaries
# ---------------------------------------------------------------------------


class TestDeriveTrueBoundaries:
    def test_no_change_returns_empty(self):
        assert derive_true_boundaries([0, 0, 0, 0], sample_length=10) == []

    def test_single_change(self):
        # labels [0, 1], sample_length=10 → boundary at 10
        assert derive_true_boundaries([0, 1], sample_length=10) == [10]

    def test_multiple_changes(self):
        labels = [0, 0, 1, 1, 0]
        result = derive_true_boundaries(labels, sample_length=5)
        assert result == [10, 20]  # at index 2 and 4

    def test_every_sample_changes(self):
        labels = [0, 1, 0, 1]
        result = derive_true_boundaries(labels, sample_length=3)
        assert result == [3, 6, 9]


# ---------------------------------------------------------------------------
# derive_true_segments
# ---------------------------------------------------------------------------


class TestDeriveTrueSegments:
    def test_single_class_run(self):
        segs = derive_true_segments([0, 0, 0], sample_length=10, label_names=["A", "B"])
        assert len(segs) == 1
        assert segs[0].start == 0
        assert segs[0].end == 29
        assert segs[0].label == "A"

    def test_two_class_runs(self):
        segs = derive_true_segments([0, 0, 1, 1], sample_length=5, label_names=["A", "B"])
        assert len(segs) == 2
        assert segs[0] == Segment(0, 9, "A")
        assert segs[1] == Segment(10, 19, "B")

    def test_alternating_classes(self):
        segs = derive_true_segments([0, 1, 0], sample_length=4, label_names=["X", "Y"])
        assert len(segs) == 3
        assert segs[0] == Segment(0, 3, "X")
        assert segs[1] == Segment(4, 7, "Y")
        assert segs[2] == Segment(8, 11, "X")

    def test_segments_cover_full_range_without_gaps(self):
        labels = [0, 1, 0, 1, 0]
        T = 6
        segs = derive_true_segments(labels, sample_length=T, label_names=["A", "B"])
        assert segs[0].start == 0
        for i in range(len(segs) - 1):
            assert segs[i].end + 1 == segs[i + 1].start
        assert segs[-1].end == len(labels) * T - 1
