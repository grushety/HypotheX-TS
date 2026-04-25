# VAL-010 — Shape-vocabulary coverage (session-level)

**Status:** [ ] Done
**Depends on:** OP-041 (label chip events), audit log

---

## Goal

Compute per-session **shape-vocabulary coverage** = `|unique shapes touched in this session| / 7`. Surfaces in the Lisnic-style "Guardrails" sidebar and warns the user when their exploration concentrates on a small subset of the 7-shape vocabulary.

**Why:** Cherry-picking risk goes up when users explore only one or two shape primitives. Forcing visibility into coverage encourages systematic exploration and reduces confirmation-bias artifacts (Wall et al. TVCG 2022; Lumos TVCG 2022).

**How it fits:** Session-level metric, computed asynchronously from the audit log stream (UI-015). Updates the Guardrails sidebar; threshold-crossing surfaces a guidance tip.

---

## Paper references (for `algorithm-auditor`)

- Wall, Narechania, Coscia, Paden, Endert, **"Left, Right, and Gender,"** IEEE TVCG 28:966 (2022) — interaction-bias metrics including Attribute Coverage.
- Narechania, Coscia, Wall, Endert, **"Lumos,"** IEEE TVCG 28:1009 (2022) — live-overlay implementation.
- Lisnic, Cutler, Kogan, Lex, **"Visualization Guardrails,"** CHI 2025, DOI 10.1145/3706598.3713385.

---

## Pseudocode

```python
@dataclass(frozen=True)
class CoverageResult:
    shapes_touched: set[str]
    coverage_fraction: float        # |touched| / 7
    most_used_shape: str
    least_used_shape: str | None    # None if all shapes equally represented
    edit_count_per_shape: dict[str, int]
    skewness: float                 # Gini-style; high = focused on one shape

class ShapeVocabularyCoverageTracker:
    SHAPES = ['plateau', 'trend', 'step', 'spike', 'cycle', 'transient', 'noise']

    def __init__(self):
        self.edit_counts = {s: 0 for s in self.SHAPES}
        self.event_log = []

    def on_label_chip_event(self, chip):
        # Count both pre-edit and post-edit shapes (an edit *touches* both)
        self.edit_counts[chip.old_shape] += 1
        if chip.new_shape != chip.old_shape:
            self.edit_counts[chip.new_shape] += 1
        self.event_log.append(chip)

    def coverage(self) -> CoverageResult:
        touched = {s for s, c in self.edit_counts.items() if c > 0}
        total = sum(self.edit_counts.values())
        if total == 0:
            return CoverageResult(set(), 0.0, '', None, self.edit_counts.copy(), 0.0)
        return CoverageResult(
            shapes_touched=touched,
            coverage_fraction=len(touched) / 7,
            most_used_shape=max(self.edit_counts, key=self.edit_counts.get),
            least_used_shape=min((s for s in touched), key=self.edit_counts.get) if len(touched) > 1 else None,
            edit_count_per_shape=self.edit_counts.copy(),
            skewness=gini_coefficient(list(self.edit_counts.values())),
        )
```

---

## Acceptance Criteria

- [ ] `backend/app/services/validation/coverage.py` with:
  - `CoverageResult` frozen dataclass
  - `ShapeVocabularyCoverageTracker` class subscribing to `label_chip` event bus topic (from OP-041)
  - Tracks both old and new shapes per chip (an edit "touches" both)
- [ ] Coverage fraction surfaced in Guardrails sidebar (UI; ticket VAL-014)
- [ ] When fraction < 0.4 AND skewness > 0.6 AND total_edits > 10, trigger tip "exploration heavily focused on `<most_used_shape>`; consider trying `<missing_shape>`" (VAL-020)
- [ ] Reset semantics: per-session OR per-CF-task (configurable; default per-session)
- [ ] Persisted across server restarts via session DB
- [ ] Tests: empty session → coverage=0; one edit on plateau → coverage=1/7, most_used='plateau'; balanced edits across 7 shapes → coverage=1, low skewness; skewed edits → high skewness
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper refs Wall 2022 (Attribute Coverage), Lumos 2022. Confirm: coverage definition matches Wall's attribute-coverage metric; Gini skewness used consistently
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "VAL-010: shape-vocabulary coverage (session-level)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
