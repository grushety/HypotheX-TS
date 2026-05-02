"""Validity-rate tracker (VAL-012).

Session-level metric: ``rate = |edits that flipped the model to target| /
|total edits committed|``. Surfaces in the Guardrails sidebar (VAL-014)
as a basic competency canary; persistently low rates fire a guidance
tip (VAL-020).

Sources (binding for ``algorithm-auditor``):

  - Verma, Boonsanong, Hoang, Hines, Dickerson, Shah,
    *ACM CSUR* 56:312 (Oct 2024), DOI:10.1145/3677119 — validity is the
    primary CF desideratum.
  - Mothilal, Sharma, Tan, "DiCE," FAccT 2020 — operationalises validity
    rate as a per-method evaluation metric.

The tracker mirrors the design of VAL-010's ``ShapeVocabularyCoverageTracker``
and VAL-011's ``IncrementalDiversityTracker``: a small in-memory counter,
optional auto-subscription to an ``EventBus`` topic, ``reset`` for the
session-vs-task choice, and ``from_events`` for the persistence-replay
constructor (no new DB column — replay the event stream from
``audit_events``).

Note on ``CFResult.predicted_class`` vs ``target_class``:
The current ``CFResult`` (OP-050) does not yet carry these fields — they
are populated by the orchestrator that calls the user's classifier
post-edit. The tracker therefore takes ``is_valid`` as an explicit
boolean on the event rather than reaching into ``CFResult`` directly;
the orchestrator that knows the target class produces the event. This
keeps the tracker decoupled from the classifier wiring.
"""
from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.services.events import EventBus

CF_RESULT_TOPIC = "cf_result"

# Mirror VAL-010's seven-shape vocabulary so per-shape breakdowns key on
# the same canonical labels.
_SHAPES: tuple[str, ...] = (
    "plateau", "trend", "step", "spike", "cycle", "transient", "noise",
)
_TIERS: tuple[int, ...] = (0, 1, 2, 3)

DEFAULT_TIP_RATE_THRESHOLD = 0.3
DEFAULT_TIP_WINDOW = 10
DEFAULT_TREND_WINDOW_SECONDS = 7 * 24 * 60 * 60  # 7 days


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CFResultEvent:
    """Per-edit validity event published on the ``'cf_result'`` topic.

    The orchestrator that runs the user's classifier post-edit constructs
    these. Keeping the boolean explicit (rather than reaching into a
    ``CFResult`` for ``predicted_class`` / ``target_class``) decouples
    this tracker from the classifier wiring that may differ across
    deployments.
    """

    is_valid: bool
    tier: int
    shape: str
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ValidityRateResult:
    """Snapshot of the session validity-rate counters.

    Attributes:
        n_total:           Total edits the tracker has seen.
        n_valid:           Edits where ``is_valid=True``.
        rate:              ``n_valid / n_total``; 0.0 when no edits.
        rate_by_tier:      Map ``tier → rate`` for every tier with at
                           least one event. Tiers with zero events are
                           omitted (no division-by-zero).
        rate_by_shape:     Map ``shape → rate`` for every shape with at
                           least one event.
        rate_trend_7day:   Rolling rate over the last 7 days; ``None``
                           when no events fall in the window. Useful as
                           a confirmation-bias canary for long-running
                           researchers.
        recent_rate:       Rate over the last ``tip_window`` events;
                           ``None`` when fewer than ``tip_window`` events
                           have been seen.
        tip_should_fire:   ``recent_rate < tip_rate_threshold`` and the
                           tracker has at least ``tip_window`` events.
                           Surfaces the VAL-020 "low CF success" tip.
        tip_window:        Window size used for ``recent_rate``;
                           reported on the result so the UI / tip engine
                           doesn't need to reach into the tracker.
        tip_rate_threshold: Threshold the rate must fall below.
    """

    n_total: int
    n_valid: int
    rate: float
    rate_by_tier: dict[int, float]
    rate_by_shape: dict[str, float]
    rate_trend_7day: float | None
    recent_rate: float | None
    tip_should_fire: bool
    tip_window: int
    tip_rate_threshold: float


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------


class ValidityRateTracker:
    """In-memory accumulator for per-session validity rate.

    Construction:

        tracker = ValidityRateTracker(event_bus=bus)

    auto-subscribes to ``bus`` for the ``'cf_result'`` topic. Pass
    ``event_bus=None`` to skip auto-subscription (e.g. in tests that
    drive the tracker directly via ``on_cf_event``).

    Events are stored as immutable ``CFResultEvent`` records. Counter
    queries (``rate``) walk the list — O(n) but n is bounded by the
    session's edit count, which in practice stays low (order 100s);
    the AC's "O(1) per event" applies to the *append* path, not query.
    """

    def __init__(
        self,
        *,
        event_bus: EventBus | None = None,
        tip_rate_threshold: float = DEFAULT_TIP_RATE_THRESHOLD,
        tip_window: int = DEFAULT_TIP_WINDOW,
        trend_window_seconds: float = DEFAULT_TREND_WINDOW_SECONDS,
        clock: Any = None,
    ) -> None:
        if not 0.0 <= tip_rate_threshold <= 1.0:
            raise ValueError(
                f"tip_rate_threshold must be in [0, 1]; got {tip_rate_threshold}"
            )
        if tip_window < 1:
            raise ValueError(f"tip_window must be ≥ 1; got {tip_window}")
        if trend_window_seconds <= 0:
            raise ValueError(
                f"trend_window_seconds must be > 0; got {trend_window_seconds}"
            )

        self.tip_rate_threshold = float(tip_rate_threshold)
        self.tip_window = int(tip_window)
        self.trend_window_seconds = float(trend_window_seconds)
        # ``clock`` lets tests pin the current time without monkeypatching.
        self._clock = clock if clock is not None else time.time

        self._events: list[CFResultEvent] = []
        self._unknown_shape_warned: set[str] = set()
        self._unknown_tier_warned: set[int] = set()
        self._event_bus = event_bus
        if event_bus is not None:
            event_bus.subscribe(CF_RESULT_TOPIC, self.on_cf_event)

    # -------- ingest -------------------------------------------------------

    def on_cf_event(self, event: Any) -> None:
        """Subscriber callback for the ``'cf_result'`` topic.

        Accepts a ``CFResultEvent`` directly or any object with the same
        four attributes (``is_valid``, ``tier``, ``shape``, ``timestamp``).
        Unknown shapes or tiers warn once and are still recorded — the
        tip predicate ignores them in the ``rate_by_*`` breakdowns but
        they do count toward the total / recent rate (an out-of-vocab op
        is still a valid attempt).
        """
        is_valid = bool(getattr(event, "is_valid"))
        tier = int(getattr(event, "tier"))
        shape = str(getattr(event, "shape"))
        ts = float(getattr(event, "timestamp", None) or self._clock())

        if shape not in _SHAPES and shape not in self._unknown_shape_warned:
            self._unknown_shape_warned.add(shape)
            warnings.warn(
                f"ValidityRateTracker: unknown shape label {shape!r}; "
                f"expected one of {_SHAPES}.",
                RuntimeWarning,
                stacklevel=2,
            )
        if tier not in _TIERS and tier not in self._unknown_tier_warned:
            self._unknown_tier_warned.add(tier)
            warnings.warn(
                f"ValidityRateTracker: unknown tier {tier!r}; expected one of {_TIERS}.",
                RuntimeWarning,
                stacklevel=2,
            )

        self._events.append(
            CFResultEvent(is_valid=is_valid, tier=tier, shape=shape, timestamp=ts)
        )

    # -------- query --------------------------------------------------------

    def rate(self) -> ValidityRateResult:
        n = len(self._events)
        if n == 0:
            return ValidityRateResult(
                n_total=0, n_valid=0, rate=0.0,
                rate_by_tier={}, rate_by_shape={},
                rate_trend_7day=None, recent_rate=None,
                tip_should_fire=False,
                tip_window=self.tip_window,
                tip_rate_threshold=self.tip_rate_threshold,
            )

        n_valid = sum(1 for e in self._events if e.is_valid)
        rate = n_valid / n

        rate_by_tier: dict[int, float] = {}
        for t in _TIERS:
            tier_events = [e for e in self._events if e.tier == t]
            if tier_events:
                rate_by_tier[t] = sum(1 for e in tier_events if e.is_valid) / len(tier_events)

        rate_by_shape: dict[str, float] = {}
        for s in _SHAPES:
            shape_events = [e for e in self._events if e.shape == s]
            if shape_events:
                rate_by_shape[s] = sum(1 for e in shape_events if e.is_valid) / len(shape_events)

        # Recent-window rate (last `tip_window` events by *insertion order*,
        # which matches the user's perception of "the last N edits I made").
        recent_rate: float | None = None
        if n >= self.tip_window:
            recent = self._events[-self.tip_window:]
            recent_rate = sum(1 for e in recent if e.is_valid) / len(recent)

        # Rolling 7-day rate: events whose timestamp is within
        # `trend_window_seconds` of "now" per the injected clock.
        cutoff = float(self._clock()) - self.trend_window_seconds
        windowed = [e for e in self._events if e.timestamp >= cutoff]
        rate_trend_7day = (
            sum(1 for e in windowed if e.is_valid) / len(windowed)
            if windowed else None
        )

        tip_should_fire = bool(
            recent_rate is not None and recent_rate < self.tip_rate_threshold
        )

        return ValidityRateResult(
            n_total=n,
            n_valid=n_valid,
            rate=rate,
            rate_by_tier=rate_by_tier,
            rate_by_shape=rate_by_shape,
            rate_trend_7day=rate_trend_7day,
            recent_rate=recent_rate,
            tip_should_fire=tip_should_fire,
            tip_window=self.tip_window,
            tip_rate_threshold=self.tip_rate_threshold,
        )

    @property
    def n_total(self) -> int:
        return len(self._events)

    @property
    def n_valid(self) -> int:
        return sum(1 for e in self._events if e.is_valid)

    # -------- lifecycle ----------------------------------------------------

    def reset(self) -> None:
        """Zero all counters; preserve the warn-cache so previously-flagged
        unknown shapes / tiers stay silent on replay."""
        self._events.clear()

    def close(self) -> None:
        """Unsubscribe from the event bus; idempotent."""
        if self._event_bus is not None:
            self._event_bus.unsubscribe(CF_RESULT_TOPIC, self.on_cf_event)
            self._event_bus = None

    @classmethod
    def from_events(
        cls,
        events: Iterable[Any],
        *,
        event_bus: EventBus | None = None,
        tip_rate_threshold: float = DEFAULT_TIP_RATE_THRESHOLD,
        tip_window: int = DEFAULT_TIP_WINDOW,
        trend_window_seconds: float = DEFAULT_TREND_WINDOW_SECONDS,
        clock: Any = None,
    ) -> "ValidityRateTracker":
        """Replay constructor — equivalent to constructing then calling
        ``on_cf_event`` for every event in order. Used at server startup
        to recover state from the persisted audit-event stream."""
        tracker = cls(
            event_bus=event_bus,
            tip_rate_threshold=tip_rate_threshold,
            tip_window=tip_window,
            trend_window_seconds=trend_window_seconds,
            clock=clock,
        )
        for event in events:
            tracker.on_cf_event(event)
        return tracker
