"""Shape-vocabulary coverage tracker (VAL-010).

Session-level metric that counts how many of the seven shape primitives
(``plateau``, ``trend``, ``step``, ``spike``, ``cycle``, ``transient``,
``noise``) the user has touched in this session. Surfaces in the
Lisnic-style Guardrails sidebar (VAL-014) and fires a tip when
exploration concentrates on a small subset.

Coverage is computed by subscribing the tracker to the ``label_chip``
event-bus topic emitted by OP-041; each chip increments the count for
its ``old_shape``, and additionally for ``new_shape`` if the op changed
the shape (an edit "touches" both pre- and post-shape, but a PRESERVED
op only touches one).

Sources (binding for ``algorithm-auditor``):

  - Wall, Narechania, Coscia, Paden, Endert, "Left, Right, and Gender,"
    *IEEE TVCG* 28:966 (2022) — interaction-bias metrics including
    Attribute Coverage; the per-shape coverage fraction is the same
    primitive applied to the 7-shape vocabulary.
  - Narechania, Coscia, Wall, Endert, "Lumos," *IEEE TVCG* 28:1009 (2022).
  - Lisnic, Cutler, Kogan, Lex, "Visualization Guardrails," CHI 2025,
    DOI:10.1145/3706598.3713385.

Gini coefficient is the standard inequality measure ``G = Σ_i Σ_j
|x_i − x_j| / (2 n Σ x)``. For seven shapes the maximum value is
``6/7 ≈ 0.857`` (all edits on one shape); a uniform spread gives 0.

Persistence note: the tracker holds in-memory counts. The "persisted
across server restarts" requirement is satisfied by ``from_chips`` —
on startup the caller replays the audit-log records (already stored in
the SQLite ``audit_events`` table) through the tracker.
"""
from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from app.services.events import EventBus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


SHAPES: tuple[str, ...] = (
    "plateau", "trend", "step", "spike", "cycle", "transient", "noise",
)
N_SHAPES = len(SHAPES)
_SHAPE_SET = frozenset(SHAPES)

LABEL_CHIP_TOPIC = "label_chip"

DEFAULT_TIP_FRACTION_THRESHOLD = 0.4
DEFAULT_TIP_SKEWNESS_THRESHOLD = 0.6
DEFAULT_TIP_MIN_EDITS = 10


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoverageResult:
    """Snapshot of the session's shape-vocabulary coverage.

    Attributes:
        shapes_touched:        ``frozenset`` of shape labels with ≥ 1 edit.
        coverage_fraction:     ``|shapes_touched| / 7`` ∈ [0, 1].
        most_used_shape:       Shape with the highest edit count; empty
                               string when no edits have happened.
        least_used_shape:      Shape with the lowest *positive* edit count;
                               ``None`` when fewer than two shapes have
                               been touched, or when all touched shapes
                               are tied at the minimum.
        edit_count_per_shape:  ``dict`` mapping every shape to its count
                               (zero for untouched shapes). Snapshot copy
                               — caller is free to mutate it.
        skewness:              Gini coefficient over the seven counts;
                               0 = uniform, ``6/7`` = fully concentrated.
        total_edits:           Sum of all per-shape counts.
        tip_should_fire:       True iff ``coverage_fraction <
                               fraction_threshold`` and ``skewness >
                               skewness_threshold`` and
                               ``total_edits > min_edits``. Threshold
                               values are reported on the result so the
                               UI / tip engine doesn't have to reach
                               into the tracker.
        suggested_shape:       A shape with zero edits (the "missing"
                               shape that the tip should suggest). Picked
                               in ``SHAPES`` order; ``None`` when every
                               shape has been touched.
    """

    shapes_touched: frozenset[str]
    coverage_fraction: float
    most_used_shape: str
    least_used_shape: str | None
    edit_count_per_shape: dict[str, int]
    skewness: float
    total_edits: int
    tip_should_fire: bool
    suggested_shape: str | None


# ---------------------------------------------------------------------------
# Gini coefficient
# ---------------------------------------------------------------------------


def gini_coefficient(values: Iterable[float]) -> float:
    """Standard Gini coefficient on a sequence of non-negative values.

    Returns 0 for an all-zero or all-equal sequence; ``(n − 1) / n`` for a
    fully concentrated sequence (one positive value, rest zero). For the
    7-shape vocabulary the maximum is ``6 / 7 ≈ 0.857``.
    """
    arr = [float(v) for v in values]
    n = len(arr)
    if n == 0:
        return 0.0
    total = sum(arr)
    if total <= 0.0:
        return 0.0
    sorted_vals = sorted(arr)
    cumulative = 0.0
    for i, v in enumerate(sorted_vals, start=1):
        cumulative += i * v
    return (2.0 * cumulative) / (n * total) - (n + 1.0) / n


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------


class ShapeVocabularyCoverageTracker:
    """In-memory accumulator for per-session shape coverage.

    Construction:

        tracker = ShapeVocabularyCoverageTracker(event_bus=bus)

    auto-subscribes to ``bus`` for the ``'label_chip'`` topic. Pass
    ``event_bus=None`` to skip auto-subscription (e.g. in tests that
    drive the tracker directly via ``on_label_chip_event``).

    Reset semantics:
      * ``reset()`` zeroes all counts. The session-vs-task choice is the
        caller's: a session-scoped guardrail calls reset on session end,
        a task-scoped guardrail on CF-task complete.

    Persistence:
      * Use ``from_chips`` to rebuild the counts from a list of historical
        ``LabelChip`` records (e.g. after a server restart). Replaying
        audit events through ``on_label_chip_event`` yields the same
        result.
    """

    def __init__(
        self,
        *,
        event_bus: EventBus | None = None,
        fraction_threshold: float = DEFAULT_TIP_FRACTION_THRESHOLD,
        skewness_threshold: float = DEFAULT_TIP_SKEWNESS_THRESHOLD,
        min_edits: int = DEFAULT_TIP_MIN_EDITS,
    ) -> None:
        if not 0.0 <= fraction_threshold <= 1.0:
            raise ValueError(
                f"fraction_threshold must be in [0, 1]; got {fraction_threshold}"
            )
        if not 0.0 <= skewness_threshold <= 1.0:
            raise ValueError(
                f"skewness_threshold must be in [0, 1]; got {skewness_threshold}"
            )
        if min_edits < 0:
            raise ValueError(f"min_edits must be ≥ 0; got {min_edits}")

        self.fraction_threshold = float(fraction_threshold)
        self.skewness_threshold = float(skewness_threshold)
        self.min_edits = int(min_edits)

        self._counts: dict[str, int] = {s: 0 for s in SHAPES}
        self._unknown_shape_warned: set[str] = set()
        self._event_bus = event_bus
        if event_bus is not None:
            event_bus.subscribe(LABEL_CHIP_TOPIC, self.on_label_chip_event)

    # -------- event handler ------------------------------------------------

    def on_label_chip_event(self, chip: Any) -> None:
        """Subscriber callback for the ``'label_chip'`` topic.

        Counts ``chip.old_shape`` once; counts ``chip.new_shape`` only
        when it differs from the old shape (an edit "touches" both
        pre- and post-shape on a transition, but a PRESERVED op stays in
        the same primitive and is one touch).
        """
        old = getattr(chip, "old_shape", None)
        new = getattr(chip, "new_shape", None)
        if old is None and new is None:
            warnings.warn(
                "ShapeVocabularyCoverageTracker.on_label_chip_event: "
                "chip has neither old_shape nor new_shape; ignoring.",
                RuntimeWarning,
                stacklevel=2,
            )
            return
        self._increment(old)
        if new is not None and new != old:
            self._increment(new)

    def _increment(self, shape: Any) -> None:
        if shape is None:
            return
        if shape not in _SHAPE_SET:
            if shape not in self._unknown_shape_warned:
                self._unknown_shape_warned.add(shape)
                warnings.warn(
                    f"ShapeVocabularyCoverageTracker: ignoring unknown shape "
                    f"label {shape!r}; expected one of {SHAPES}.",
                    RuntimeWarning,
                    stacklevel=3,
                )
            return
        self._counts[shape] += 1

    # -------- query --------------------------------------------------------

    def coverage(self) -> CoverageResult:
        counts_snapshot = dict(self._counts)
        total = sum(counts_snapshot.values())
        touched = frozenset(s for s, c in counts_snapshot.items() if c > 0)

        if total == 0:
            return CoverageResult(
                shapes_touched=touched,
                coverage_fraction=0.0,
                most_used_shape="",
                least_used_shape=None,
                edit_count_per_shape=counts_snapshot,
                skewness=0.0,
                total_edits=0,
                tip_should_fire=False,
                suggested_shape=SHAPES[0],
            )

        # Most used: tie-break by SHAPES order (stable).
        most_used = max(SHAPES, key=lambda s: (counts_snapshot[s], -SHAPES.index(s)))

        # Least used among touched shapes: only meaningful when ≥ 2 shapes
        # have been touched and there is a unique minimum.
        least_used: str | None = None
        if len(touched) >= 2:
            touched_counts = [(counts_snapshot[s], SHAPES.index(s), s) for s in touched]
            min_count = min(c for c, _, _ in touched_counts)
            at_min = [s for c, _, s in touched_counts if c == min_count]
            if len(at_min) == 1:
                least_used = at_min[0]

        coverage_fraction = len(touched) / N_SHAPES
        skewness = gini_coefficient(counts_snapshot.values())
        suggested = next((s for s in SHAPES if counts_snapshot[s] == 0), None)

        tip_fire = bool(
            coverage_fraction < self.fraction_threshold
            and skewness > self.skewness_threshold
            and total > self.min_edits
        )

        return CoverageResult(
            shapes_touched=touched,
            coverage_fraction=coverage_fraction,
            most_used_shape=most_used,
            least_used_shape=least_used,
            edit_count_per_shape=counts_snapshot,
            skewness=skewness,
            total_edits=total,
            tip_should_fire=tip_fire,
            suggested_shape=suggested,
        )

    # -------- lifecycle ----------------------------------------------------

    def reset(self) -> None:
        """Zero all counts; warn-cache is preserved (callers expect
        previously-flagged unknown shapes to stay quiet)."""
        for s in SHAPES:
            self._counts[s] = 0

    def close(self) -> None:
        """Unsubscribe from the event bus; idempotent."""
        if self._event_bus is not None:
            self._event_bus.unsubscribe(LABEL_CHIP_TOPIC, self.on_label_chip_event)
            self._event_bus = None

    # -------- replay -------------------------------------------------------

    @classmethod
    def from_chips(
        cls,
        chips: Iterable[Any],
        *,
        event_bus: EventBus | None = None,
        fraction_threshold: float = DEFAULT_TIP_FRACTION_THRESHOLD,
        skewness_threshold: float = DEFAULT_TIP_SKEWNESS_THRESHOLD,
        min_edits: int = DEFAULT_TIP_MIN_EDITS,
    ) -> "ShapeVocabularyCoverageTracker":
        """Rebuild a tracker from a stream of historical LabelChip records.

        Used at server startup to recover state from the persisted
        audit log: the chips replay produces the same counts as the
        live session would have produced.
        """
        tracker = cls(
            event_bus=event_bus,
            fraction_threshold=fraction_threshold,
            skewness_threshold=skewness_threshold,
            min_edits=min_edits,
        )
        for chip in chips:
            tracker.on_label_chip_event(chip)
        return tracker

    # -------- introspection ------------------------------------------------

    @property
    def edit_counts(self) -> Mapping[str, int]:
        """Read-only view of the current per-shape counts."""
        return dict(self._counts)
