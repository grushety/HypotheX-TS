## Ticket Header

**Ticket ID:** `HTS-302`  
**Title:** `Implement structural segment operations`  
**Status:** `done`  
**Priority:** `P0`  
**Type:** `feature`  
**Depends on:** `HTS-301`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-302-structural-operations`

---

## 1. Goal

Implement the MVP structural operations over segmentation state: edit boundary, split, merge, and reclassify. These are the minimum semantic editing actions the interface needs before value-level operations or model assistance become useful.

---

## 2. Scope

### In scope
- EditBoundary
- Split
- Merge
- Reclassify
- state validation and integration with legality/constraint checks

### Out of scope
- value-space operations on the time series signal
- UI interaction behavior
- model suggestions

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `MyPaper-HypotheX-TS - Semantic Chunk Types and Typed Operation - Revised.md`
- `HypotheX-TS - Formal Definitions.md`
- `HypotheX-TS - Technical Plan.md`

---

## 4. Affected Areas

### Likely files or modules
- `backend/services/operations/structural.py`
- `backend/services/segmentation_state.py`
- `tests/`

### Architecture layer
Mark all that apply:
- [ ] frontend
- [x] backend
- [x] API contract
- [x] domain logic
- [ ] model/data
- [x] tests
- [ ] docs

### Risk level
`high`

Brief reason:
> These are core user-visible actions. Off-by-one and adjacency bugs are likely if the boundary semantics are not handled carefully.

---

## 5. Inputs and Expected Outputs

### Inputs
- current segmentation state
- operation request payload
- constraint mode and registry

### Expected outputs
- updated segmentation state
- operation result payload
- history/audit-ready metadata

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [x] EditBoundary updates only the adjacent segments involved in the moved boundary.
- [x] Split produces two contiguous child segments with valid boundaries.
- [x] Merge combines only adjacent compatible segments and preserves coverage.
- [x] Reclassify changes only the label and preserves boundaries.
- [x] Invalid structural operations do not corrupt state and return explicit feedback.

---

## 7. Implementation Notes

- Use the shared legality and constraint engine rather than duplicating rules.
- Be explicit about inclusive boundary semantics.
- Record enough metadata for later audit logging.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [x] operation unit tests
- [x] integration tests with state service
- [x] lint/static checks

### Commands
```bash
pytest -q
ruff check .
```

### Manual verification
1. Boundary-edit two adjacent segments.
2. Split one segment and inspect children.
3. Merge them back and confirm original coverage is restored.

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

- structural operations service
- tests for valid/invalid edits
- updated service wiring

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
**What changed:** `added a backend structural-operations service for boundary edit, split, merge, and reclassify; integrated legality and constraint evaluation before state commits; added unit and state-integration tests for valid and invalid structural edits`  
**Checks run:** `C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests/test_structural_operations.py, C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests, C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\ruff.exe check backend schemas docs`  
**Blockers:** `none`  
**Next step:** `HTS-303`

---

## 14. Completion Note

**Completed on:** `2026-03-28`  
**Summary:** `Implemented backend structural segment operations with explicit success and denial results, constraint-gated state commits, and history-ready metadata for edit-boundary, split, merge, and reclassify flows.`  
**Tests passed:** `C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests/test_structural_operations.py; C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests; C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\ruff.exe check backend schemas docs`  
**Files changed:** `backend/app/services/operations/structural.py, backend/app/services/operations/__init__.py, backend/app/services/__init__.py, backend/tests/test_structural_operations.py, tickets/mvp/HTS-302 - Implement structural segment operations.md`  
**Follow-up tickets needed:** `none`
