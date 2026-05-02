"""Tests for VAL-010: Shape-vocabulary coverage tracker.

Covers:
 - empty session → coverage 0, total_edits 0, suggested_shape='plateau'
 - single plateau edit → coverage 1/7, most_used='plateau'
 - balanced one-edit-per-shape → coverage 1, low Gini, no tip
 - heavily skewed → high Gini, tip fires when fraction < 0.4 + > min_edits
 - PRESERVED op (old==new) counts shape ONCE
 - DETERMINISTIC op (old!=new) counts BOTH shapes
 - reset() zeros counts
 - event-bus subscription delivers chips automatically
 - close() unsubscribes; subsequent publishes are ignored
 - from_chips replays history and produces the same counts
 - unknown shape labels are ignored with a warning (one warning per label)
 - tip_should_fire false when min_edits not met
 - DTO frozen + threshold validation
 - gini_coefficient sanity (zero-input, all-equal, fully concentrated)
"""
from __future__ import annotations

import warnings

import pytest

from app.services.events import EventBus
from app.services.operations.relabeler.label_chip import LabelChip
from app.services.operations.relabeler.relabeler import RelabelResult
from app.services.validation import (
    DEFAULT_TIP_FRACTION_THRESHOLD,
    DEFAULT_TIP_MIN_EDITS,
    DEFAULT_TIP_SKEWNESS_THRESHOLD,
    LABEL_CHIP_TOPIC,
    N_SHAPES,
    SHAPES,
    CoverageResult,
    ShapeVocabularyCoverageTracker,
    gini_coefficient,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _chip(old: str, new: str | None = None,
          *, op_name: str = "raise_lower", tier: int = 2,
          confidence: float = 1.0,
          rule_class: str = "PRESERVED") -> LabelChip:
    new = new if new is not None else old
    return LabelChip(
        segment_id="seg-test",
        op_id="op-test",
        op_name=op_name,
        tier=tier,
        old_shape=old,
        new_shape=new,
        confidence=confidence,
        rule_class=rule_class,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Gini coefficient
# ---------------------------------------------------------------------------


class TestGini:
    def test_empty(self):
        assert gini_coefficient([]) == 0.0

    def test_all_zero(self):
        assert gini_coefficient([0, 0, 0]) == 0.0

    def test_uniform(self):
        assert gini_coefficient([3, 3, 3, 3]) == pytest.approx(0.0, abs=1e-9)

    def test_fully_concentrated(self):
        # Single positive, six zeros over 7 entries → max Gini = (n-1)/n = 6/7
        assert gini_coefficient([10, 0, 0, 0, 0, 0, 0]) == pytest.approx(6 / 7, abs=1e-9)

    def test_monotone_in_concentration(self):
        spread = gini_coefficient([5, 5, 5, 5, 5, 5, 5])
        moderate = gini_coefficient([10, 5, 5, 5, 5, 5, 5])
        skewed = gini_coefficient([20, 5, 5, 5, 5, 5, 5])
        assert spread <= moderate <= skewed


# ---------------------------------------------------------------------------
# Tracker — basic state
# ---------------------------------------------------------------------------


class TestTrackerBasic:
    def test_empty_session(self):
        t = ShapeVocabularyCoverageTracker()
        result = t.coverage()
        assert result.coverage_fraction == 0.0
        assert result.total_edits == 0
        assert result.shapes_touched == frozenset()
        assert result.most_used_shape == ""
        assert result.least_used_shape is None
        # Suggested shape on empty session is the first SHAPES entry (plateau)
        assert result.suggested_shape == "plateau"
        assert result.tip_should_fire is False

    def test_single_plateau_edit(self):
        t = ShapeVocabularyCoverageTracker()
        t.on_label_chip_event(_chip("plateau", "plateau"))
        result = t.coverage()
        assert result.coverage_fraction == pytest.approx(1.0 / N_SHAPES)
        assert result.total_edits == 1
        assert result.most_used_shape == "plateau"
        assert result.shapes_touched == frozenset({"plateau"})
        assert result.least_used_shape is None  # only one shape touched

    def test_preserved_op_counts_once(self):
        t = ShapeVocabularyCoverageTracker()
        t.on_label_chip_event(_chip("plateau", "plateau", rule_class="PRESERVED"))
        assert t.edit_counts["plateau"] == 1
        # No double-count
        assert sum(t.edit_counts.values()) == 1

    def test_deterministic_op_counts_both(self):
        t = ShapeVocabularyCoverageTracker()
        t.on_label_chip_event(_chip("plateau", "trend", rule_class="DETERMINISTIC"))
        assert t.edit_counts["plateau"] == 1
        assert t.edit_counts["trend"] == 1
        assert sum(t.edit_counts.values()) == 2

    def test_balanced_full_coverage(self):
        t = ShapeVocabularyCoverageTracker()
        for s in SHAPES:
            t.on_label_chip_event(_chip(s, s))
        result = t.coverage()
        assert result.coverage_fraction == 1.0
        assert result.shapes_touched == frozenset(SHAPES)
        assert result.skewness == pytest.approx(0.0, abs=1e-9)
        assert result.suggested_shape is None
        assert result.tip_should_fire is False

    def test_least_used_unique_minimum(self):
        t = ShapeVocabularyCoverageTracker()
        # plateau: 5, trend: 1 → least is trend (unique min)
        for _ in range(5):
            t.on_label_chip_event(_chip("plateau", "plateau"))
        t.on_label_chip_event(_chip("trend", "trend"))
        result = t.coverage()
        assert result.least_used_shape == "trend"

    def test_least_used_none_on_tie(self):
        t = ShapeVocabularyCoverageTracker()
        for _ in range(3):
            t.on_label_chip_event(_chip("plateau", "plateau"))
            t.on_label_chip_event(_chip("trend", "trend"))
        # Tied at 3-3 → least_used None per docstring
        assert t.coverage().least_used_shape is None


# ---------------------------------------------------------------------------
# Tip firing
# ---------------------------------------------------------------------------


class TestTipFiring:
    def test_skewed_above_threshold_fires(self):
        # 11 plateau edits → coverage 1/7 ≈ 0.143 < 0.4, gini ≈ 6/7 > 0.6, total > 10
        t = ShapeVocabularyCoverageTracker()
        for _ in range(11):
            t.on_label_chip_event(_chip("plateau", "plateau"))
        result = t.coverage()
        assert result.tip_should_fire is True
        assert result.suggested_shape is not None
        assert result.suggested_shape != "plateau"

    def test_below_min_edits_does_not_fire(self):
        # 5 plateau edits → skewed but total < 10
        t = ShapeVocabularyCoverageTracker()
        for _ in range(5):
            t.on_label_chip_event(_chip("plateau", "plateau"))
        result = t.coverage()
        assert result.total_edits == 5
        assert result.tip_should_fire is False

    def test_high_coverage_does_not_fire(self):
        t = ShapeVocabularyCoverageTracker()
        # Touch many shapes — coverage above 0.4 disables the tip
        for s in SHAPES[:4]:
            for _ in range(3):
                t.on_label_chip_event(_chip(s, s))
        result = t.coverage()
        assert result.coverage_fraction >= 0.4
        assert result.tip_should_fire is False

    def test_thresholds_validated_on_construction(self):
        with pytest.raises(ValueError, match="fraction_threshold"):
            ShapeVocabularyCoverageTracker(fraction_threshold=1.5)
        with pytest.raises(ValueError, match="skewness_threshold"):
            ShapeVocabularyCoverageTracker(skewness_threshold=-0.1)
        with pytest.raises(ValueError, match="min_edits"):
            ShapeVocabularyCoverageTracker(min_edits=-1)

    def test_default_thresholds_match_ac(self):
        assert DEFAULT_TIP_FRACTION_THRESHOLD == 0.4
        assert DEFAULT_TIP_SKEWNESS_THRESHOLD == 0.6
        assert DEFAULT_TIP_MIN_EDITS == 10


# ---------------------------------------------------------------------------
# Reset + close + replay
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_reset_zeros_counts(self):
        t = ShapeVocabularyCoverageTracker()
        for _ in range(3):
            t.on_label_chip_event(_chip("plateau", "trend", rule_class="DETERMINISTIC"))
        t.reset()
        assert sum(t.edit_counts.values()) == 0
        assert t.coverage().total_edits == 0

    def test_event_bus_subscription(self):
        bus = EventBus()
        t = ShapeVocabularyCoverageTracker(event_bus=bus)
        bus.publish(LABEL_CHIP_TOPIC, _chip("plateau", "trend",
                                            rule_class="DETERMINISTIC"))
        bus.publish(LABEL_CHIP_TOPIC, _chip("trend", "trend"))
        assert t.edit_counts["plateau"] == 1
        assert t.edit_counts["trend"] == 2

    def test_close_unsubscribes(self):
        bus = EventBus()
        t = ShapeVocabularyCoverageTracker(event_bus=bus)
        bus.publish(LABEL_CHIP_TOPIC, _chip("plateau", "plateau"))
        t.close()
        bus.publish(LABEL_CHIP_TOPIC, _chip("trend", "trend"))
        # plateau counted (before close), trend NOT counted (after close)
        assert t.edit_counts["plateau"] == 1
        assert t.edit_counts["trend"] == 0

    def test_close_idempotent(self):
        bus = EventBus()
        t = ShapeVocabularyCoverageTracker(event_bus=bus)
        t.close()
        t.close()  # should not raise

    def test_from_chips_rebuilds_state(self):
        history = [
            _chip("plateau", "plateau"),
            _chip("plateau", "trend", rule_class="DETERMINISTIC"),
            _chip("trend", "trend"),
            _chip("spike", "spike"),
        ]
        t = ShapeVocabularyCoverageTracker.from_chips(history)
        assert t.edit_counts["plateau"] == 2
        assert t.edit_counts["trend"] == 2
        assert t.edit_counts["spike"] == 1

    def test_from_chips_matches_live_replay(self):
        history = [
            _chip("plateau", "trend", rule_class="DETERMINISTIC"),
            _chip("cycle", "cycle"),
            _chip("noise", "noise"),
        ]
        replayed = ShapeVocabularyCoverageTracker.from_chips(history)
        live = ShapeVocabularyCoverageTracker()
        for chip in history:
            live.on_label_chip_event(chip)
        assert dict(replayed.edit_counts) == dict(live.edit_counts)


# ---------------------------------------------------------------------------
# Unknown / malformed inputs
# ---------------------------------------------------------------------------


class TestRobustness:
    def test_unknown_shape_warns_once(self):
        t = ShapeVocabularyCoverageTracker()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            t.on_label_chip_event(_chip("unknown_shape", "unknown_shape"))
            t.on_label_chip_event(_chip("unknown_shape", "unknown_shape"))
        # First call warns; second call is silent (cache hit)
        unknown_warnings = [w for w in caught if "unknown_shape" in str(w.message)]
        assert len(unknown_warnings) == 1
        assert sum(t.edit_counts.values()) == 0  # never incremented

    def test_chip_without_shapes_warns(self):
        class _Empty:
            pass
        t = ShapeVocabularyCoverageTracker()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            t.on_label_chip_event(_Empty())
        assert any("old_shape" in str(w.message) or "new_shape" in str(w.message)
                   for w in caught)


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


class TestCoverageResultDTO:
    def test_frozen(self):
        r = CoverageResult(
            shapes_touched=frozenset(),
            coverage_fraction=0.0,
            most_used_shape="",
            least_used_shape=None,
            edit_count_per_shape={s: 0 for s in SHAPES},
            skewness=0.0,
            total_edits=0,
            tip_should_fire=False,
            suggested_shape="plateau",
        )
        with pytest.raises((AttributeError, TypeError)):
            r.coverage_fraction = 1.0  # type: ignore[misc]

    def test_edit_count_snapshot_is_independent(self):
        t = ShapeVocabularyCoverageTracker()
        t.on_label_chip_event(_chip("plateau", "plateau"))
        snap = t.coverage().edit_count_per_shape
        snap["plateau"] = 999
        assert t.edit_counts["plateau"] == 1


# ---------------------------------------------------------------------------
# Integration with real LabelChip from emit_label_chip
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_via_emit_label_chip(self):
        """End-to-end: emit_label_chip publishes a LabelChip, the tracker
        receives and counts it."""
        from app.services.operations.relabeler.label_chip import emit_label_chip

        bus = EventBus()
        t = ShapeVocabularyCoverageTracker(event_bus=bus)

        relabel = RelabelResult(
            new_shape="trend", confidence=1.0,
            needs_resegment=False, rule_class="DETERMINISTIC",
        )
        emit_label_chip(
            segment_id="s",
            op_id="op",
            op_name="replace_with_trend",
            tier=2,
            old_shape="plateau",
            relabel_result=relabel,
            event_bus=bus,
        )
        assert t.edit_counts["plateau"] == 1
        assert t.edit_counts["trend"] == 1
