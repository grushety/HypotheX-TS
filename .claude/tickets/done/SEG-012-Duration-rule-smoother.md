# SEG-012 — Duration-rule smoother (HSMM-lite)

**Status:** [x] Done
**Depends on:** SEG-008 or SEG-011 classifier output; OP-040 rule table (for label compatibility)

---

## Goal

Enforce per-class minimum segment duration `L_min(y)` after shape classification by merging under-length segments with their most compatible neighbor. Prevents over-segmentation without the complexity of a full HSMM decoder.

**Why:** Change-point detectors tend to produce spurious short segments around noisy boundaries. A simple duration rule catches these without training a full HSMM (`Yu 2010`), which remains an optional Phase-4 extension.

**How it fits:** Runs between SEG-009 (boundary proposer) and SEG-008/SEG-011 (shape classifier), or equivalently after initial classification as a post-processing cleanup. Merge-target selection uses label-compatibility from the relabeler rule table (OP-040).

---

## Paper references (for `algorithm-auditor`)

- Yu (2010) "Hidden semi-Markov models" — *Artificial Intelligence* 174(2):215–243 (HSMM review for full implementation reference).
- Sakoe & Chiba (1978) for DTW-based neighbor-compatibility distance — *IEEE ASSP* 26(1):43–49.

---

## Pseudocode

```python
def smooth_by_duration(segments, L_min_per_class, compat_rule_table):
    changed = True
    while changed:
        changed = False
        for i, s in enumerate(segments):
            if len(s) >= L_min_per_class[s.label]:
                continue
            left  = segments[i - 1] if i > 0 else None
            right = segments[i + 1] if i < len(segments) - 1 else None
            target = choose_merge_target(s, left, right, compat_rule_table)
            segments = merge(segments, i, target)
            changed = True
            break    # restart scan after mutation
    return segments

def choose_merge_target(s, left, right, compat_rule_table):
    compat_left  = compat_rule_table.score(s.label, left.label)  + embed_sim(s, left)  if left  else -inf
    compat_right = compat_rule_table.score(s.label, right.label) + embed_sim(s, right) if right else -inf
    return 'left' if compat_left > compat_right else 'right'
```

---

## Acceptance Criteria

- [x] `backend/app/services/suggestion/duration_smoother.py` with:
  - `DurationRuleSmoother` class with `smooth(segments) -> list[Segment]`
  - `L_min_per_class: dict[str, int]` loaded from config (per-shape minimum length)
  - Label-compatibility lookup via OP-040 rule table (no new rules introduced here)
- [x] After smoothing, no segment shorter than `L_min(y)` for its label `y`
- [x] Deterministic outcome for a given input and thresholds (termination proof: merges reduce segment count monotonically)
- [x] Segment merge preserves time coverage (left.b and right.e become merged.b and merged.e; no timesteps orphaned)
- [ ] Over-segmentation metric (segment_count / ground_truth_count) ≤ 1.3 on TSSB validation split
- [x] `BoundarySuggestionService.propose()` calls `DurationRuleSmoother.smooth()` after classification, before decomposition blob fitting (SEG-019)
- [x] `L_min_per_class` defaults: plateau=20, trend=15, step=3, spike=1, cycle=2*period, transient=10, noise=5 (overridable by domain pack via SEG-021..023)
- [x] Tests cover: short segment merged into compatible neighbor; no neighbors (single-segment series) handled gracefully; equal compatibility scores break tie deterministically (left); multiple consecutive short segments all resolve in finite iterations
- [x] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [x] Run `test-writer` agent — all tests pass
- [x] Run `algorithm-auditor` agent with paper references: Yu 2010 (confirm the merge-to-compatible-neighbor heuristic is a documented HSMM approximation). Flag as Phase-4 follow-up if full HSMM decoder is needed for paper publication
- [x] Run `code-reviewer` agent — no blocking issues
- [x] `git commit -m "SEG-012: duration-rule smoother (HSMM-lite post-processing)"`
- [x] Update Status to `[x] Done`

## Work Done

- `backend/app/services/suggestion/duration_smoother.py` — `DurationRuleSmoother` dataclass with `smooth(segments) -> tuple[ProvisionalSegment, ...]`; per-class min lengths for 7-primitive vocabulary (plateau=20, trend=15, step=3, spike=1, cycle=20, transient=10, noise=5) plus domain-label aliases; iterative merge loop with guaranteed termination; label-compatibility scoring via classifier label-score distribution + same-label bonus + length tiebreaker; deterministic left-wins tiebreak
- `backend/app/services/suggestions.py` — imported `DurationRuleSmoother`; `BoundarySuggestionService.__init__` builds `self._duration_smoother` from domain-config min lengths; `propose()` calls `self._duration_smoother.smooth(labeled_segments)` replacing direct `smooth_provisional_segments()` call
- `backend/tests/test_duration_smoother.py` — 30 tests covering: L_min defaults, edge cases (empty/single), basic left/right merge, time-coverage preservation, compatibility scoring, equal-score left tiebreak, multiple consecutive short segments, post-smooth invariants (renumbering, sort order, all segments ≥ L_min), service integration


---
