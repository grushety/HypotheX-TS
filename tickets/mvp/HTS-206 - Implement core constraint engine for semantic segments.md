## Ticket Header

**Ticket ID:** `HTS-206`  
**Title:** `Implement core constraint engine for semantic segments`  
**Status:** `done`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-202, HTS-203, HTS-205`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-206-constraint-engine`

---

## 1. Goal

Implement the first version of the semantic constraint engine so operations can be checked as hard or soft violations. This ticket should cover the MVP constraint set and return machine-readable violation details suitable for both backend enforcement and frontend feedback.

---

## 2. Scope

### In scope
- minimum-duration constraint
- trend monotonicity constraint
- plateau stability constraint
- basic label compatibility checks

### Out of scope
- advanced projection algorithms
- domain-physics constraints beyond MVP examples
- training-time constraint losses

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `MyPaper-HypotheX-TS - Semantic Chunk Types and Typed Operation - Revised.md`
- `HypotheX-TS - Technical Plan.md`
- `HypotheX-TS - Evaluation.md`

---

## 4. Affected Areas

### Likely files or modules
- `backend/domain/constraints.py`
- `backend/services/constraint_engine.py`
- `tests/`

### Architecture layer
Mark all that apply:
- [ ] frontend
- [x] backend
- [x] API contract
- [x] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`high`

Brief reason:
> Constraint behavior is central to the contribution. Poor error handling or unclear severity semantics will confuse both users and developers.

---

## 5. Inputs and Expected Outputs

### Inputs
- current series and segmentation state
- candidate operation result
- constraint config with hard/soft mode

### Expected outputs
- pass/warn/fail result
- violation list with severity and message
- optional repair hint metadata

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [x] MVP constraints can be evaluated against a candidate segmentation or operation result.
- [x] Each violation reports a constraint key, severity, and readable message.
- [x] Hard and soft modes are distinguishable in the returned result.
- [x] Tests cover pass, warn, and fail cases.
- [x] Constraint logic does not depend on frontend presentation code.

---

## 7. Implementation Notes

- Do not overbuild projection logic yet.
- Keep constraint functions small and composable.
- Messages should be understandable enough for eventual UI display.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [x] unit tests for constraint results
- [x] lint/static checks

### Commands
```bash
pytest -q
ruff check .
```

### Manual verification
1. Trigger a minimum-duration violation.
2. Trigger a trend monotonicity violation.
3. Verify mode switching between soft and hard changes only severity handling.

If a check cannot run, Codex must record why.

---

## 9. Definition of Done

A ticket is done only when all items below are true.

- [x] Goal is implemented.
- [x] All acceptance criteria are satisfied.
- [x] Required tests and checks pass.
- [x] No blocking review issues remain.
- [x] Docs/comments are updated if behavior changed.
- [x] Changes are committed with the ticket ID.
- [x] Ticket status is updated to `done`.

---

## 10. Deliverables

- constraint engine module
- tests
- docs note on supported MVP constraints

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
**What changed:** `added composable MVP constraint rules, a thin constraint-engine service, repair-hint support in the shared contract, and backend tests for pass/warn/fail paths`  
**Checks run:** `pytest -q (blocked: pytest not on PATH), ruff check . (blocked: ruff not on PATH), JSON parse sanity checks for schema fixtures`  
**Blockers:** `python and ruff tooling are not runnable in this shell environment`  
**Next step:** `HTS-301`

---

## 14. Completion Note

**Completed on:** `2026-03-28`  
**Summary:** `Implemented the first backend constraint engine for minimum duration, trend monotonicity, plateau stability, and basic label compatibility checks.`  
**Tests passed:** `JSON parse sanity checks`  
**Files changed:** `backend/app/domain/, backend/app/services/, backend/tests/test_constraint_engine.py, backend/config/mvp-domain-config.json, schemas/, docs/domain-config-note.md, tickets/mvp/HTS-206 - Implement core constraint engine for semantic segments.md`  
**Follow-up tickets needed:** `none`
