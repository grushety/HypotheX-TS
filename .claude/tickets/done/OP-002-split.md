# OP-002 — split (Tier 0)

**Status:** [x] Done
**Depends on:** —

---

## Goal

Split a segment at a user-chosen `t*` into two new contiguous segments. Both halves inherit the parent's shape label until the relabeler (OP-040) runs on them independently.

**Why:** Users need to disagree with the classifier's segment boundaries — the most common correction is "this looks like two different things." Without `split`, the user can only delete and start over.

**How it fits:** Tier 0 structural op. Called by UI-004 (right-click or palette). Invalidates decomposition blobs on both halves and queues them for refit via SEG-019 dispatcher.

---

## Paper references

N/A — structural. See [[_project HypotheX-TS/HypotheX-TS - Formal Definitions]] §5.0.

---

## Pseudocode

```python
def split(segments, k, t_star):
    s = segments[k]
    if not (s.b < t_star < s.e):
        raise InvalidEdit(f"split point {t_star} outside segment [{s.b}, {s.e}]")

    left  = Segment(b=s.b,        e=t_star,     label=s.label, scope=s.scope,
                    confidence=s.confidence, provenance='user')
    right = Segment(b=t_star + 1, e=s.e,        label=s.label, scope=s.scope,
                    confidence=s.confidence, provenance='user')
    left.decomposition  = None   # mark dirty
    right.decomposition = None

    enqueue_refit(left)
    enqueue_refit(right)

    segments[k:k + 1] = [left, right]
    return segments
```

---

## Acceptance Criteria

- [x] `backend/app/services/operations/tier0/split.py` with:
  - `split(segments, k, t_star) -> list[Segment]`
  - Raises `InvalidEdit` if `t_star` not strictly inside `[segments[k].b, segments[k].e]`
  - Both halves respect `L_min` for the parent label (else raise before mutation)
- [x] Both halves inherit parent's shape label, scope, and provenance=`user`; confidence carried over (relabeler will update later)
- [x] Decomposition blobs set to `None` for both halves (modelled as `decomposition_dirty=True`); refit queued by caller via SEG-019 dispatcher
- [x] Audit entry: deferred to service-layer caller (pure function has no I/O)
- [x] Tests cover: valid split; boundary split (t_star = b+1, t_star = e-1) respects L_min; invalid split raises; decomposition blobs invalidated on both halves
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `test-writer` agent — 25 tests pass; two misleadingly-named tests renamed before commit
- [x] Run `algorithm-auditor` agent — left.end_index + 1 == right.start_index invariant confirmed correct; transaction semantics and L_min ordering verified
- [x] Run `code-reviewer` agent — no blocking issues
- [x] `git commit -m "OP-002: split (Tier 0 structural op)"`
- [x] Update Status to `[x] Done`

## Work Done

- `backend/app/services/operations/tier0/edit_boundary.py` — extended `Segment` with `provenance: str = "user"`, `confidence: float | None = None`, `scope: str | None = None` to support split inheritance
- `backend/app/services/operations/tier0/split.py` — pure function `split(segments, k, t_star) -> list[Segment]`; validates t_star strictly inside, validates L_min for both halves before any mutation, sets `decomposition_dirty=True` on both children, inherits label/scope/confidence from parent with `provenance="user"`
- `backend/app/services/operations/tier0/__init__.py` — exports `split`
- `backend/tests/test_tier0_split.py` — 25 tests: valid split structure, contiguity, provenance/label/confidence/scope inheritance, dirty flags, first/last segment edges, invalid t_star (at bounds and outside), L_min violations on both halves, event L_min, no-mutation on failure


---
