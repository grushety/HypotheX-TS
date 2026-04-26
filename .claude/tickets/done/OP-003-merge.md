# OP-003 — merge (Tier 0)

**Status:** [x] Done
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

- [x] `backend/app/services/operations/tier0/merge.py` with:
  - `merge(segments, k, X, *, relabeler=None) -> list[Segment]`
  - Raises `InvalidEdit` if `k` is out of range or no right neighbour exists
  - Calls OP-040 relabeler with both source labels; never uses simple majority
- [x] Merged segment spans `[left.start_index, right.end_index]` exactly; both source segments removed
- [x] Scope inheritance: left segment's scope wins (documented in docstring)
- [x] Decomposition blob set to dirty=True, refit queued via SEG-019 dispatcher at caller
- [x] Audit entry: deferred to service-layer caller (pure function has no I/O); relabeler rule_class is in RelabelResult
- [x] Edge case: merged segment that violates L_min is allowed (can only arise from pre-existing violation)
- [x] Tests cover: merge two plateaus → plateau; merge trend + plateau → relabeler decides (not majority); invalid k raises; scope inheritance; decomposition dirty; relabeler arguments verified
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `test-writer` agent — all 24 tests pass; all 5 required cases covered
- [x] Run `algorithm-auditor` agent — merged span, relabeler-always-called, transaction semantics, scope-left-wins, series-slice all confirmed correct
- [x] Run `code-reviewer` agent — no blocking issues
- [x] `git commit -m "OP-003: merge (Tier 0 structural op)"`
- [x] Update Status to `[x] Done`

## Work Done

- `backend/app/services/operations/relabeler/__init__.py` — new package for OP-040 relabeler; exports `RelabelResult`, `default_relabeler`
- `backend/app/services/operations/relabeler/relabeler.py` — `RelabelResult` frozen dataclass; `RelabelerFn` type alias; `default_relabeler()` implementing the RECLASSIFY_VIA_SEGMENTER path via RuleBasedShapeClassifier (SEG-008); injectable for testing
- `backend/app/services/operations/tier0/merge.py` — pure function `merge(segments, k, X, *, relabeler=None, domain_config=None) -> list[Segment]`; validates k range; calls relabeler with (old_shape, 'merge', {neighbour_label}, merged_series); scope from left, provenance='user', decomposition_dirty=True; transaction-safe via candidate list
- `backend/app/services/operations/tier0/__init__.py` — exports `merge`
- `backend/tests/test_tier0_merge.py` — 24 tests: segment count, span, id format, label/confidence/provenance from relabeler, decomposition dirty, scope inheritance (left wins / None propagated), relabeler called with correct args (old_shape, operation, op_params, series length, exactly once), invalid k variants, no-mutation on failure, first/last pair merge


---
