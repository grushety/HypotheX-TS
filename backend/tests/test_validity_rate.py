"""Tests for VAL-012: Validity-rate tracker.

Covers:
 - empty tracker → rate=0, n_total=0, no tip
 - one valid edit → rate=1
 - mixed → correct overall rate
 - per-tier breakdown only includes tiers with events
 - per-shape breakdown only includes shapes with events
 - rolling 7-day excludes old events; injected clock makes this deterministic
 - tip predicate: < 0.3 over last 10 → fires; below 10 events → does not fire
 - reset clears state
 - close() unsubscribes; subsequent publishes ignored
 - from_events replays history identically to live add
 - subscription via event bus delivers events
 - unknown shape / tier warns once and is still recorded
 - DTO frozen + threshold validation
"""
from __future__ import annotations

import warnings

import pytest

from app.services.events import EventBus
from app.services.validation import (
    CF_RESULT_TOPIC,
    DEFAULT_TIP_RATE_THRESHOLD,
    DEFAULT_TIP_WINDOW,
    CFResultEvent,
    ValidityRateResult,
    ValidityRateTracker,
)


# ---------------------------------------------------------------------------
# Fixed-clock helper
# ---------------------------------------------------------------------------


class _Clock:
    """Tiny fixed-clock for deterministic 7-day-window tests."""

    def __init__(self, t: float) -> None:
        self.t = float(t)

    def __call__(self) -> float:
        return self.t


def _ev(valid: bool, tier: int = 2, shape: str = "plateau",
        ts: float | None = None) -> CFResultEvent:
    return CFResultEvent(
        is_valid=valid, tier=tier, shape=shape,
        timestamp=ts if ts is not None else 1_700_000_000.0,
    )


# ---------------------------------------------------------------------------
# Tracker — basic rate
# ---------------------------------------------------------------------------


class TestRateBasic:
    def test_empty(self):
        t = ValidityRateTracker()
        r = t.rate()
        assert r.n_total == 0
        assert r.n_valid == 0
        assert r.rate == 0.0
        assert r.rate_by_tier == {}
        assert r.rate_by_shape == {}
        assert r.rate_trend_7day is None
        assert r.recent_rate is None
        assert r.tip_should_fire is False

    def test_one_valid_edit(self):
        t = ValidityRateTracker()
        t.on_cf_event(_ev(valid=True))
        r = t.rate()
        assert r.n_total == 1
        assert r.n_valid == 1
        assert r.rate == 1.0
        assert r.rate_by_tier == {2: 1.0}
        assert r.rate_by_shape == {"plateau": 1.0}

    def test_one_invalid_edit(self):
        t = ValidityRateTracker()
        t.on_cf_event(_ev(valid=False))
        r = t.rate()
        assert r.n_total == 1
        assert r.n_valid == 0
        assert r.rate == 0.0

    def test_mixed_rate(self):
        t = ValidityRateTracker()
        for v in [True, True, False, True, False]:
            t.on_cf_event(_ev(valid=v))
        r = t.rate()
        assert r.n_total == 5
        assert r.n_valid == 3
        assert r.rate == 0.6


# ---------------------------------------------------------------------------
# Per-tier / per-shape breakdown
# ---------------------------------------------------------------------------


class TestBreakdown:
    def test_per_tier_only_includes_seen_tiers(self):
        t = ValidityRateTracker()
        t.on_cf_event(_ev(valid=True, tier=1))
        t.on_cf_event(_ev(valid=False, tier=1))
        t.on_cf_event(_ev(valid=True, tier=2))
        r = t.rate()
        # Only tiers 1 and 2 in breakdown; tiers 0 and 3 omitted.
        assert set(r.rate_by_tier) == {1, 2}
        assert r.rate_by_tier[1] == 0.5
        assert r.rate_by_tier[2] == 1.0

    def test_per_shape_only_includes_seen_shapes(self):
        t = ValidityRateTracker()
        t.on_cf_event(_ev(valid=True, shape="plateau"))
        t.on_cf_event(_ev(valid=False, shape="plateau"))
        t.on_cf_event(_ev(valid=True, shape="trend"))
        r = t.rate()
        assert set(r.rate_by_shape) == {"plateau", "trend"}
        assert r.rate_by_shape["plateau"] == 0.5
        assert r.rate_by_shape["trend"] == 1.0

    def test_per_tier_sum_consistency(self):
        """Σ(events with tier == t) over all t equals n_total."""
        t = ValidityRateTracker()
        events = [
            _ev(True, tier=1), _ev(False, tier=1),
            _ev(True, tier=2), _ev(True, tier=2),
            _ev(False, tier=3),
        ]
        for e in events:
            t.on_cf_event(e)
        r = t.rate()
        # rate_by_tier reports rate, but we can verify by reconstructing counts
        total_tracked = 0
        for tier_id, rate_val in r.rate_by_tier.items():
            tier_events = [e for e in events if e.tier == tier_id]
            total_tracked += len(tier_events)
            n_valid = sum(1 for e in tier_events if e.is_valid)
            assert rate_val == pytest.approx(n_valid / len(tier_events))
        assert total_tracked == r.n_total


# ---------------------------------------------------------------------------
# Rolling 7-day trend (deterministic via injected clock)
# ---------------------------------------------------------------------------


class TestRolling7Day:
    def test_excludes_events_older_than_7_days(self):
        clock = _Clock(1_700_000_000.0)
        t = ValidityRateTracker(clock=clock)
        # Old event: 10 days ago, valid
        t.on_cf_event(_ev(valid=True, ts=clock.t - 10 * 86400))
        # Recent: 1 day ago, invalid
        t.on_cf_event(_ev(valid=False, ts=clock.t - 1 * 86400))
        # Recent: 2 hours ago, valid
        t.on_cf_event(_ev(valid=True, ts=clock.t - 2 * 3600))
        r = t.rate()
        # Overall rate: 2/3
        assert r.rate == pytest.approx(2 / 3)
        # 7-day rolling: only the two recent events; 1 valid out of 2 → 0.5
        assert r.rate_trend_7day == pytest.approx(0.5)

    def test_no_recent_events_returns_none(self):
        clock = _Clock(1_700_000_000.0)
        t = ValidityRateTracker(clock=clock)
        # Single event 30 days ago
        t.on_cf_event(_ev(valid=True, ts=clock.t - 30 * 86400))
        r = t.rate()
        assert r.rate_trend_7day is None

    def test_clock_advance_phases_out_events(self):
        clock = _Clock(1_700_000_000.0)
        t = ValidityRateTracker(clock=clock)
        t.on_cf_event(_ev(valid=True, ts=clock.t - 1 * 86400))
        assert t.rate().rate_trend_7day == 1.0
        # Advance the clock past 7 days; event is now out of window
        clock.t += 8 * 86400
        assert t.rate().rate_trend_7day is None


# ---------------------------------------------------------------------------
# Tip predicate
# ---------------------------------------------------------------------------


class TestTipPredicate:
    def test_low_recent_rate_fires(self):
        t = ValidityRateTracker(tip_window=10, tip_rate_threshold=0.3)
        # 10 events with 2 valid → 20% < 30%
        for i in range(10):
            t.on_cf_event(_ev(valid=(i < 2)))
        r = t.rate()
        assert r.recent_rate == pytest.approx(0.2)
        assert r.tip_should_fire is True

    def test_below_window_size_does_not_fire(self):
        t = ValidityRateTracker(tip_window=10, tip_rate_threshold=0.3)
        # Only 5 events, all invalid → low rate but n < tip_window
        for _ in range(5):
            t.on_cf_event(_ev(valid=False))
        r = t.rate()
        assert r.recent_rate is None
        assert r.tip_should_fire is False

    def test_recent_rate_above_threshold_does_not_fire(self):
        t = ValidityRateTracker(tip_window=10, tip_rate_threshold=0.3)
        # 10 events with 8 valid → 80% > 30%
        for i in range(10):
            t.on_cf_event(_ev(valid=(i < 8)))
        r = t.rate()
        assert r.recent_rate == pytest.approx(0.8)
        assert r.tip_should_fire is False

    def test_window_uses_only_last_N(self):
        """Old failures don't affect the recent-window rate once enough
        successes follow."""
        t = ValidityRateTracker(tip_window=5, tip_rate_threshold=0.5)
        for _ in range(10):
            t.on_cf_event(_ev(valid=False))  # all bad
        for _ in range(5):
            t.on_cf_event(_ev(valid=True))  # last 5 all good
        r = t.rate()
        assert r.recent_rate == 1.0
        assert r.tip_should_fire is False

    def test_default_thresholds_match_ac(self):
        assert DEFAULT_TIP_RATE_THRESHOLD == 0.3
        assert DEFAULT_TIP_WINDOW == 10

    def test_invalid_threshold_rejected(self):
        with pytest.raises(ValueError, match="tip_rate_threshold"):
            ValidityRateTracker(tip_rate_threshold=1.5)
        with pytest.raises(ValueError, match="tip_window"):
            ValidityRateTracker(tip_window=0)
        with pytest.raises(ValueError, match="trend_window_seconds"):
            ValidityRateTracker(trend_window_seconds=0)


# ---------------------------------------------------------------------------
# Lifecycle: reset, close, replay
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_reset_clears_state(self):
        t = ValidityRateTracker()
        for _ in range(3):
            t.on_cf_event(_ev(valid=True))
        t.reset()
        r = t.rate()
        assert r.n_total == 0
        assert r.rate == 0.0

    def test_subscription_delivers_events(self):
        bus = EventBus()
        t = ValidityRateTracker(event_bus=bus)
        bus.publish(CF_RESULT_TOPIC, _ev(valid=True))
        bus.publish(CF_RESULT_TOPIC, _ev(valid=False))
        r = t.rate()
        assert r.n_total == 2

    def test_close_unsubscribes(self):
        bus = EventBus()
        t = ValidityRateTracker(event_bus=bus)
        bus.publish(CF_RESULT_TOPIC, _ev(valid=True))
        t.close()
        bus.publish(CF_RESULT_TOPIC, _ev(valid=True))
        assert t.rate().n_total == 1  # only first publish counted

    def test_close_idempotent(self):
        bus = EventBus()
        t = ValidityRateTracker(event_bus=bus)
        t.close()
        t.close()  # should not raise

    def test_from_events_replay(self):
        events = [
            _ev(True, tier=1, shape="plateau"),
            _ev(False, tier=2, shape="trend"),
            _ev(True, tier=2, shape="trend"),
        ]
        replayed = ValidityRateTracker.from_events(events)
        live = ValidityRateTracker()
        for e in events:
            live.on_cf_event(e)
        assert replayed.rate().rate == live.rate().rate
        assert replayed.rate().rate_by_tier == live.rate().rate_by_tier


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


class TestRobustness:
    def test_unknown_shape_warns_once(self):
        t = ValidityRateTracker()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            t.on_cf_event(_ev(valid=True, shape="bogus_shape"))
            t.on_cf_event(_ev(valid=False, shape="bogus_shape"))
        msgs = [str(w.message) for w in caught if "bogus_shape" in str(w.message)]
        assert len(msgs) == 1  # one warning per unknown label
        # Events still counted toward total
        assert t.rate().n_total == 2

    def test_unknown_tier_warns_once(self):
        t = ValidityRateTracker()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            t.on_cf_event(_ev(valid=True, tier=99))
            t.on_cf_event(_ev(valid=False, tier=99))
        msgs = [str(w.message) for w in caught if "99" in str(w.message)]
        assert len(msgs) == 1

    def test_duck_typed_event_accepted(self):
        """Any object with the four expected attributes works."""
        class _Stub:
            is_valid = True
            tier = 2
            shape = "plateau"
            timestamp = 1_700_000_000.0
        t = ValidityRateTracker()
        t.on_cf_event(_Stub())
        assert t.rate().n_total == 1


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


class TestDTOs:
    def test_event_frozen(self):
        e = CFResultEvent(is_valid=True, tier=2, shape="plateau", timestamp=0.0)
        with pytest.raises((AttributeError, TypeError)):
            e.is_valid = False  # type: ignore[misc]

    def test_result_frozen(self):
        r = ValidityRateResult(
            n_total=0, n_valid=0, rate=0.0,
            rate_by_tier={}, rate_by_shape={},
            rate_trend_7day=None, recent_rate=None,
            tip_should_fire=False, tip_window=10, tip_rate_threshold=0.3,
        )
        with pytest.raises((AttributeError, TypeError)):
            r.rate = 1.0  # type: ignore[misc]

    def test_event_default_timestamp_uses_clock(self):
        e = CFResultEvent(is_valid=True, tier=2, shape="plateau")
        # Just check it is finite — not asserting exact value
        assert isinstance(e.timestamp, float) and e.timestamp > 0
