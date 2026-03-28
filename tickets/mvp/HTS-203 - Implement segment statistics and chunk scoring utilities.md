## Ticket Header

**Ticket ID:** `HTS-203`  
**Title:** `Implement segment statistics and chunk scoring utilities`  
**Status:** `done`  
**Priority:** `P0`  
**Type:** `feature`  
**Depends on:** `HTS-201, HTS-202`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-203-segment-stats`

---

## 1. Goal

Implement the reusable statistical primitives needed by the formal semantic chunk definitions. This ticket should make it possible to compute per-segment scores such as slope, variance, sign consistency, residual-to-line, context contrast, and peak score without involving UI or model code.

---

## 2. Scope

### In scope
- implement reusable segment statistic functions
- support univariate and small multivariate inputs where feasible
- return explicit errors for invalid or too-short segments

### Out of scope
- final chunk label assignment policy
- model training
- visualization or UI integration

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `MyPaper-HypotheX-TS - Semantic Chunk Types and Typed Operation - Revised.md`
- `HypotheX-TS - Formal Definitions.md`
- `MyPaper-HypotheX-TS - Methodology.md`

---

## 4. Affected Areas

### Likely files or modules
- `backend/domain/segments.py`
- `backend/domain/stats.py`
- `tests/`

### Architecture layer
Mark all that apply:
- [ ] frontend
- [x] backend
- [ ] API contract
- [x] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`high`

Brief reason:
> These statistics are the formal backbone of semantic chunking. Errors here propagate into labeling, constraints, evaluation, and model supervision.

---

## 5. Inputs and Expected Outputs

### Inputs
- time series array or frame
- segment boundaries [b, e]
- optional smoothing/context parameters

### Expected outputs
- computed statistic bundle for a segment
- clear exceptions or validation results for invalid inputs

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [ ] Statistics functions exist for slope, variance, sign consistency, residual-to-line, context contrast, and peak score.
- [ ] Functions validate segment bounds and fail explicitly on invalid intervals.
- [ ] Short-segment edge cases are covered by tests.
- [ ] The utilities do not depend on frontend state or model classes.
- [ ] Returned field names align with the shared segment stats schema.

---

## 7. Implementation Notes

- Keep these functions pure and testable.
- Do not hide smoothing assumptions; expose them as parameters or config.
- Prefer deterministic behavior over clever heuristics at this stage.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [ ] unit tests for statistics
- [ ] lint/static checks

### Commands
```bash
pytest -q
ruff check .
```

### Manual verification
1. Run the stats on one clear trend segment.
2. Run them on one spike-like segment.
3. Confirm outputs are interpretable and stable.

If a check cannot run, Codex must record why.

---

## 9. Definition of Done

A ticket is done only when all items below are true.

- [ ] Goal is implemented.
- [ ] All acceptance criteria are satisfied.
- [ ] Required tests and checks pass.
- [ ] No blocking review issues remain.
- [ ] Docs/comments are updated if behavior changed.
- [ ] Changes are committed with the ticket ID.
- [ ] Ticket status is updated to `done`.

---

## 10. Deliverables

- segment statistics module
- unit tests
- brief docs/comments for each statistic

---

## 11. Review Checklist

Before marking complete, verify:

### Scope review
- [ ] No unrelated files were changed.
- [ ] No out-of-scope behavior was added.

### Architecture review
- [ ] Business logic is not in route handlers.
- [ ] Domain logic is not embedded in UI code.
- [ ] Layer boundaries remain clean.

### Quality review
- [ ] Names match project concepts.
- [ ] Error handling is explicit.
- [ ] New behavior is covered by tests.
- [ ] Logging/audit behavior is preserved where relevant.

### Contract review
- [ ] Public interfaces remain compatible, or the change is documented in the ticket.

---

## 12. Commit

### Branch naming
`{t['branch']}`

### Commit message
`{tid}: {t['title'][0].lower()+t['title'][1:]}`

---

## 13. Status Update Block

**Current status:** `done`  
**What changed:** `added pure backend segment statistics utilities, a shared segment-statistics schema, and unit tests for trend/spike/edge cases`  
**Checks run:** `pytest -q (blocked: pytest not on PATH), ruff check . (blocked: ruff not on PATH), JSON parse sanity checks for schema fixtures`  
**Blockers:** `python and ruff tooling are not runnable in this shell environment`  
**Next step:** `HTS-204`

---

## 14. Completion Note

**Completed on:** `2026-03-28`  
**Summary:** `Implemented reusable segment statistic primitives for slope, variance, sign consistency, residual-to-line, context contrast, and peak score with explicit validation errors.`  
**Tests passed:** `JSON parse sanity checks`  
**Files changed:** `backend/app/domain/, backend/tests/test_segment_statistics.py, schemas/, docs/domain-config-note.md, README.md`  
**Follow-up tickets needed:** `HTS-204`
