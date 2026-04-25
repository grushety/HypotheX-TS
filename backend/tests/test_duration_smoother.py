"""Tests for DurationRuleSmoother (SEG-012 HSMM-lite post-processing)."""

from __future__ import annotations

import pytest

from app.services.suggestion.boundary_proposal import ProvisionalSegment
from app.services.suggestion.duration_smoother import (
    DurationRuleSmoother,
    _DEFAULT_L_MIN,
    _compatibility,
    _seg_len,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seg(
    seg_id: str,
    start: int,
    end: int,
    label: str | None = None,
    confidence: float | None = None,
    label_scores: dict[str, float] | None = None,
) -> ProvisionalSegment:
    return ProvisionalSegment(
        segmentId=seg_id,
        startIndex=start,
        endIndex=end,
        label=label,
        confidence=confidence,
        labelScores=label_scores,
    )


def _smoother(**overrides) -> DurationRuleSmoother:
    return DurationRuleSmoother(**overrides)


# ---------------------------------------------------------------------------
# Default L_min values
# ---------------------------------------------------------------------------

class TestDefaultLMin:
    def test_all_7_primitives_present(self):
        for label in ("plateau", "trend", "step", "spike", "cycle", "transient", "noise"):
            assert label in _DEFAULT_L_MIN, f"Missing default for {label}"

    def test_spike_is_shortest(self):
        assert _DEFAULT_L_MIN["spike"] == 1

    def test_plateau_is_longest(self):
        assert _DEFAULT_L_MIN["plateau"] >= 15

    def test_step_short(self):
        assert _DEFAULT_L_MIN["step"] <= 5

    def test_get_min_length_returns_default_for_unknown_label(self):
        smoother = DurationRuleSmoother()
        assert smoother.get_min_length("bogus_label") == smoother.default_min_length

    def test_get_min_length_none_returns_default(self):
        smoother = DurationRuleSmoother()
        assert smoother.get_min_length(None) == smoother.default_min_length

    def test_get_min_length_known_label(self):
        smoother = DurationRuleSmoother()
        assert smoother.get_min_length("plateau") == _DEFAULT_L_MIN["plateau"]


# ---------------------------------------------------------------------------
# Empty / single-segment pass-through
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_returns_empty(self):
        smoother = DurationRuleSmoother()
        result = smoother.smooth([])
        assert result == ()

    def test_single_segment_returned_unchanged(self):
        s = _seg("segment-001", 0, 100, label="trend", confidence=0.9)
        smoother = DurationRuleSmoother()
        result = smoother.smooth([s])
        assert len(result) == 1
        assert result[0].startIndex == 0
        assert result[0].endIndex == 100

    def test_single_short_segment_returned_unchanged(self):
        # No neighbor to merge into — single segment always passes through.
        s = _seg("segment-001", 0, 0, label="plateau", confidence=0.8)
        smoother = DurationRuleSmoother()
        result = smoother.smooth([s])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Basic merge: short segment merges into neighbor
# ---------------------------------------------------------------------------

class TestBasicMerge:
    def test_short_merged_into_left_neighbor(self):
        smoother = DurationRuleSmoother(
            L_min_per_class={"plateau": 20, "trend": 5},
            default_min_length=5,
        )
        segs = [
            _seg("s1", 0, 24, label="plateau", confidence=0.9,
                 label_scores={"plateau": 0.9, "trend": 0.1}),
            _seg("s2", 25, 27, label="trend", confidence=0.7,
                 label_scores={"plateau": 0.8, "trend": 0.2}),
        ]
        result = smoother.smooth(segs)
        assert len(result) == 1
        assert result[0].startIndex == 0
        assert result[0].endIndex == 27
        assert result[0].label == "plateau"

    def test_short_merged_into_right_neighbor(self):
        smoother = DurationRuleSmoother(
            L_min_per_class={"trend": 5, "noise": 5},
            default_min_length=5,
        )
        segs = [
            _seg("s1", 0, 2, label="trend", confidence=0.6,
                 label_scores={"trend": 0.3, "noise": 0.7}),
            _seg("s2", 3, 30, label="noise", confidence=0.85,
                 label_scores={"trend": 0.1, "noise": 0.9}),
        ]
        result = smoother.smooth(segs)
        assert len(result) == 1
        assert result[0].startIndex == 0
        assert result[0].endIndex == 30
        assert result[0].label == "noise"

    def test_time_coverage_preserved_after_merge(self):
        smoother = DurationRuleSmoother(
            L_min_per_class={"step": 3},
            default_min_length=5,
        )
        segs = [
            _seg("s1", 0, 19, label="trend"),
            _seg("s2", 20, 21, label="step"),   # 2 samples < min 3
            _seg("s3", 22, 40, label="trend"),
        ]
        result = smoother.smooth(segs)
        # All timesteps 0..40 must be covered
        covered = set()
        for seg in result:
            covered.update(range(seg.startIndex, seg.endIndex + 1))
        assert covered == set(range(41))

    def test_no_timesteps_orphaned(self):
        smoother = DurationRuleSmoother(
            L_min_per_class={"spike": 1},
            default_min_length=4,
        )
        segs = [
            _seg("s1", 0, 5, label="plateau"),
            _seg("s2", 6, 7, label="trend"),  # 2 < 4
            _seg("s3", 8, 15, label="plateau"),
        ]
        result = smoother.smooth(segs)
        total = sum(s.endIndex - s.startIndex + 1 for s in result)
        assert total == 16  # 0..15


# ---------------------------------------------------------------------------
# Compatibility and tiebreak
# ---------------------------------------------------------------------------

class TestCompatibilityAndTiebreak:
    def test_same_label_preferred(self):
        target = _seg("t", 0, 5, label="trend",
                      label_scores={"trend": 0.5, "plateau": 0.5})
        same = _seg("n1", 6, 20, label="trend", confidence=0.8)
        diff = _seg("n2", 6, 20, label="plateau", confidence=0.8)
        assert _compatibility(target, same) > _compatibility(target, diff)

    def test_label_scores_used(self):
        target = _seg("t", 0, 5, label="noise",
                      label_scores={"trend": 0.8, "noise": 0.2})
        trend_neighbor = _seg("n1", 6, 20, label="trend", confidence=0.7)
        noise_neighbor = _seg("n2", 6, 20, label="noise", confidence=0.7)
        assert _compatibility(target, trend_neighbor) > _compatibility(target, noise_neighbor)

    def test_equal_scores_tiebreak_to_left(self):
        # Build a 3-segment scenario where left and right are equally compatible
        smoother = DurationRuleSmoother(
            L_min_per_class={"trend": 10},
            default_min_length=10,
        )
        segs = [
            _seg("s1", 0, 19, label="plateau", confidence=0.8),
            _seg("s2", 20, 24, label="trend"),   # 5 samples < min 10, no scores
            _seg("s3", 25, 44, label="plateau", confidence=0.8),
        ]
        result = smoother.smooth(segs)
        # Tiebreak: left wins → merged segment starts at 0
        assert len(result) == 2 or len(result) == 1  # merged happens
        merged = [s for s in result if s.endIndex == 24 or s.startIndex == 20]
        # The short segment (20-24) should be absorbed by the left (0-19)
        assert any(s.startIndex == 0 and s.endIndex == 24 for s in result)

    def test_rightward_merge_when_right_is_clearly_better(self):
        # s1 is long enough, s2 is too short; right neighbor shares label with s2
        smoother = DurationRuleSmoother(
            L_min_per_class={"plateau": 1, "trend": 5},
            default_min_length=1,
        )
        segs = [
            _seg("s1", 0, 9, label="plateau", confidence=0.9,
                 label_scores={"plateau": 0.9, "trend": 0.1}),
            _seg("s2", 10, 12, label="trend", confidence=0.9,
                 label_scores={"trend": 0.9, "plateau": 0.1}),   # 3 < 5 → too short
            _seg("s3", 13, 29, label="trend", confidence=0.9,
                 label_scores={"trend": 0.9, "plateau": 0.1}),
        ]
        result = smoother.smooth(segs)
        # s2 should merge right into s3: same label + high label score
        assert any(s.startIndex == 10 and s.endIndex == 29 for s in result)


# ---------------------------------------------------------------------------
# Multiple consecutive short segments resolve in finite iterations
# ---------------------------------------------------------------------------

class TestMultipleShortSegments:
    def test_all_short_segments_resolve(self):
        smoother = DurationRuleSmoother(
            L_min_per_class={"trend": 10},
            default_min_length=10,
        )
        # 5 consecutive 3-sample segments — all below min 10
        segs = [_seg(f"s{i}", i * 3, i * 3 + 2, label="trend") for i in range(5)]
        result = smoother.smooth(segs)
        for seg in result:
            assert seg.endIndex - seg.startIndex + 1 >= 10 or len(result) == 1

    def test_terminates_finite_time(self):
        # A stress case: 20 1-sample segments
        smoother = DurationRuleSmoother(
            L_min_per_class={"noise": 5},
            default_min_length=5,
        )
        segs = [_seg(f"s{i}", i, i, label="noise") for i in range(20)]
        result = smoother.smooth(segs)
        assert len(result) >= 1
        # All timesteps 0..19 covered
        covered = set()
        for s in result:
            covered.update(range(s.startIndex, s.endIndex + 1))
        assert covered == set(range(20))

    def test_two_under_length_in_a_row(self):
        smoother = DurationRuleSmoother(
            L_min_per_class={"step": 5},
            default_min_length=5,
        )
        segs = [
            _seg("s1", 0, 19, label="plateau", confidence=0.9),
            _seg("s2", 20, 22, label="step"),    # 3 < 5
            _seg("s3", 23, 25, label="step"),    # 3 < 5
            _seg("s4", 26, 45, label="plateau", confidence=0.9),
        ]
        result = smoother.smooth(segs)
        for seg in result:
            assert seg.endIndex - seg.startIndex + 1 >= smoother.get_min_length(seg.label)


# ---------------------------------------------------------------------------
# Post-smoothing invariants
# ---------------------------------------------------------------------------

class TestPostSmoothInvariants:
    def test_output_segments_are_renumbered_from_001(self):
        smoother = DurationRuleSmoother(
            L_min_per_class={"trend": 5},
            default_min_length=5,
        )
        segs = [
            _seg("s1", 0, 10, label="trend"),
            _seg("s2", 11, 12, label="trend"),  # 2 < 5, will merge
            _seg("s3", 13, 25, label="trend"),
        ]
        result = smoother.smooth(segs)
        for i, seg in enumerate(result, start=1):
            assert seg.segmentId == f"segment-{i:03d}"

    def test_output_sorted_by_start_index(self):
        smoother = DurationRuleSmoother(default_min_length=1)
        segs = [
            _seg("s1", 0, 9, label="plateau"),
            _seg("s2", 10, 19, label="trend"),
            _seg("s3", 20, 29, label="noise"),
        ]
        result = smoother.smooth(segs)
        starts = [s.startIndex for s in result]
        assert starts == sorted(starts)

    def test_no_segment_shorter_than_l_min_after_smoothing(self):
        smoother = DurationRuleSmoother(
            L_min_per_class={"plateau": 10, "trend": 8, "noise": 4},
            default_min_length=4,
        )
        import numpy as np
        rng = np.random.default_rng(42)
        labels = ["plateau", "trend", "noise", "plateau", "trend"]
        boundaries = sorted(rng.integers(1, 80, 4).tolist())
        starts = [0] + boundaries
        ends = boundaries + [99]
        segs = [
            _seg(f"s{i}", s, e, label=labels[i % len(labels)])
            for i, (s, e) in enumerate(zip(starts, ends))
        ]
        result = smoother.smooth(segs)
        for seg in result:
            assert _seg_len(seg) >= smoother.get_min_length(seg.label)


# ---------------------------------------------------------------------------
# Integration: BoundarySuggestionService uses DurationRuleSmoother
# ---------------------------------------------------------------------------

class TestServiceIntegration:
    def test_service_has_duration_smoother(self):
        from app.services.suggestions import BoundarySuggestionService  # noqa: PLC0415
        svc = BoundarySuggestionService()
        assert hasattr(svc, "_duration_smoother")
        assert isinstance(svc._duration_smoother, DurationRuleSmoother)
