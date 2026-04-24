# OP-002 — split (Tier 0)

**Status:** [ ] Done
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

- [ ] `backend/app/services/operations/tier0/split.py` with:
  - `split(segments, k, t_star) -> list[Segment]`
  - Raises `InvalidEdit` if `t_star` not strictly inside `[segments[k].b, segments[k].e]`
  - Both halves respect `L_min` for the parent label (else raise before mutation)
- [ ] Both halves inherit parent's shape label, scope, and provenance=`user`; confidence carried over (relabeler will update later)
- [ ] Decomposition blobs set to `None` for both halves; both queued for refit via SEG-019
- [ ] Audit entry records `{op: 'split', tier: 0, parent_segment_id, t_star, left_id, right_id}`
- [ ] Tests cover: valid split; boundary split (t_star = b+1, t_star = e-1) respects L_min; invalid split raises; decomposition blobs invalidated on both halves
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent — confirm non-overlapping property (left.e + 1 == right.b); structural only
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "OP-002: split (Tier 0 structural op)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
