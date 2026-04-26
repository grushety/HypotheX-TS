# OP-001 — edit_boundary (Tier 0)

**Status:** [x] Done
**Depends on:** SEG-012 (L_min per class)

---

## Goal

Move a segment boundary by `(δ_b, δ_e)` subject to contiguity and per-class minimum-duration constraints. Propagates changes to adjacent segments and marks affected decomposition blobs for refit.

**Why:** User-facing boundary manipulation is the foundational Tier-0 operation. Without it, users cannot correct classifier errors at segment edges. This is the simplest operation to ship and unblocks UI-005 + UI-006.

**How it fits:** Tier 0 — label-agnostic structural op. Called by UI-004 (drag-boundary handle) and UI-005 (palette button). Does not change any segment label but invalidates decomposition blobs of affected segments.

---

## Paper references

N/A — structural operation; design follows [[_project HypotheX-TS/HypotheX-TS - Formal Definitions]] §5.0.

---

## Pseudocode

```python
def edit_boundary(segments, k, delta_b=0, delta_e=0, L_min):
    s        = segments[k]
    new_b    = s.b + delta_b
    new_e    = s.e + delta_e

    # Propagate to neighbours to preserve contiguity
    if k > 0:
        segments[k - 1].e = new_b - 1
    if k < len(segments) - 1:
        segments[k + 1].b = new_e + 1
    s.b, s.e = new_b, new_e

    # Validate post-edit
    for s_check in filter(None, [
        segments[k - 1] if k > 0 else None,
        segments[k],
        segments[k + 1] if k < len(segments) - 1 else None,
    ]):
        if len(s_check) < L_min[s_check.label]:
            raise InvalidEdit(
                f"segment {s_check.id} length {len(s_check)} < L_min {L_min[s_check.label]}"
            )

    for s_affected in [segments[max(0, k - 1)], segments[k], segments[min(len(segments) - 1, k + 1)]]:
        mark_decomposition_dirty(s_affected)

    return segments
```

---

## Acceptance Criteria

- [x] `backend/app/services/operations/tier0/edit_boundary.py` with:
  - `edit_boundary(segments, k, delta_b, delta_e) -> list[Segment]`
  - Raises `InvalidEdit` with explanatory message on min-duration violation
  - Transaction semantics: if validation fails, no segment is mutated
- [x] Propagation to adjacent segments preserves `segments[k-1].e + 1 == segments[k].b` and `segments[k].e + 1 == segments[k+1].b`
- [x] Affected segments (up to 3) have `decomposition_blob.dirty = True`
- [x] Audit entry emitted via OP-041: deferred — OP-041 explicitly excludes Tier-0 boundary edits from LabelChip emission; audit is handled by the service layer via AuditLogService
- [x] Edge case: moving boundary of first/last segment respects series start/end
- [x] Tests cover: successful edit; L_min violation rolled back; first-segment edge; last-segment edge; propagation correctness
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `test-writer` agent — all tests pass (19/19)
- [x] Run `algorithm-auditor` agent — contiguity invariants correct; minor gaps (negative-index guard, inverted-boundary guard) fixed before commit
- [x] Run `code-reviewer` agent — no blocking issues
- [x] `git commit -m "OP-001: edit_boundary (Tier 0 structural op)"`
- [x] Update Status to `[x] Done`

## Work Done

- `backend/app/services/operations/tier0/__init__.py` — package init; exports `InvalidEdit`, `Segment`, `edit_boundary`
- `backend/app/services/operations/tier0/edit_boundary.py` — pure domain function `edit_boundary(segments, k, delta_b, delta_e) -> list[Segment]`; frozen `Segment` dataclass with `decomposition_dirty` flag; `InvalidEdit` exception; per-class L_min lookup from domain config; transaction semantics via candidate list; guards for negative start-index and inverted boundaries
- `backend/tests/test_tier0_edit_boundary.py` — 19 tests covering: successful mid-segment edit, left/right propagation, contiguity invariant, dirty-flag marking, original immutability, L_min violation on target and neighbour, per-label limits (event, periodic), first-segment edge, last-segment edge, single-segment, negative-index guard, inverted-boundary guard


---
