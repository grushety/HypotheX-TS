# OP-003 — merge (Tier 0)

**Status:** [ ] Done
**Depends on:** OP-040 (relabeler for merge-result shape)

---

## Goal

Combine two adjacent segments into one. The resulting shape label is determined by the relabeler (OP-040), not by simple majority or parent-label inheritance.

**Why:** When a classifier over-segments, the user needs to merge a 3-sample sliver into its neighbour. The result's shape is not a fixed rule: merging two plateau segments yields a plateau, but merging a spike into a plateau might yield a plateau-with-spike-absorbed, which the relabeler decides by re-inspecting the merged series.

**How it fits:** Tier 0 structural op. Called by UI-004 (drag one segment over its neighbour) and UI-005 (palette button after multi-select). Invalidates decomposition blob and queues for refit.

---

## Paper references

N/A — structural. See [[_project HypotheX-TS/HypotheX-TS - Formal Definitions]] §5.0.

---

## Pseudocode

```python
def merge(segments, k, X):
    if k >= len(segments) - 1:
        raise InvalidEdit(f"cannot merge segment {k} with non-existent right neighbour")
    left, right = segments[k], segments[k + 1]
    merged = Segment(
        b=left.b, e=right.e,
        scope=left.scope,                       # earlier-segment scope wins
        provenance='user',
    )
    # Relabeler decides final shape (calls SEG-008 classifier internally for RECLASSIFY case)
    new_label, confidence, needs_reseg = relabel(
        old_shape=left.label,
        operation='merge',
        op_params={'neighbour_label': right.label},
        edited_series=X[left.b : right.e + 1],
    )
    merged.label = new_label
    merged.confidence = confidence
    merged.decomposition = None
    enqueue_refit(merged)

    segments[k : k + 2] = [merged]
    return segments
```

---

## Acceptance Criteria

- [ ] `backend/app/services/operations/tier0/merge.py` with:
  - `merge(segments, k, X) -> list[Segment]`
  - Raises `InvalidEdit` if `k` is out of range or no right neighbour exists
  - Calls OP-040 relabeler with both source labels; never uses simple majority
- [ ] Merged segment spans `[left.b, right.e]` exactly; both source segments removed
- [ ] Scope inheritance: earlier segment's scope wins (documented)
- [ ] Decomposition blob set to `None`, refit queued via SEG-019
- [ ] Audit entry records both source labels, merged label, relabeler rule class, confidence
- [ ] Edge case: merging produces a segment that violates `L_min`? Only possible if already violated — allow and log warning
- [ ] Tests cover: merge two plateaus → plateau; merge trend + plateau → relabeler decides; invalid k raises; scope inheritance; audit fields correct
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent — confirm relabeler is called for every merge; structural invariants preserved
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "OP-003: merge (Tier 0 structural op)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
