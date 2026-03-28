## Ticket Header

**Ticket ID:** `HTS-303`  
**Title:** `Implement MVP typed value operations on semantic chunks`  
**Status:** `done`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-302`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-303-typed-value-ops`

---

## 1. Goal

Implement the first semantic value-space operations on the time series signal so the interface can move beyond boundary editing. The MVP should support only the smallest useful set aligned with the current formalization and operation palette.

---

## 2. Scope

### In scope
- ShiftLevel for plateau
- ChangeSlope for trend
- ScaleSpike and SuppressSpike for spike
- ShiftEvent and RemoveEvent for event

### Out of scope
- full counterfactual optimization
- advanced periodic or transition operations
- operation-aware learning

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
- `backend/services/operations/value_ops.py`
- `backend/domain/signal_transforms.py`
- `tests/`

### Architecture layer
Mark all that apply:
- [ ] frontend
- [x] backend
- [ ] API contract
- [x] domain logic
- [ ] model/data
- [x] tests
- [ ] docs

### Risk level
`medium`

Brief reason:
> Signal transforms can silently change semantics if implemented loosely. The MVP must stay conservative.

---

## 5. Inputs and Expected Outputs

### Inputs
- current series
- selected segment
- typed operation and parameters
- constraint mode

### Expected outputs
- edited signal and/or updated segment state
- validation result
- operation metadata for logging

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [x] Each MVP typed operation is implemented for its intended chunk type.
- [x] Illegal chunk-type/operation combinations are rejected before mutation.
- [x] At least one edge case per operation is tested.
- [x] Operations preserve unaffected regions of the series.
- [x] Constraint feedback remains available after the value edit.

---

## 7. Implementation Notes

- Keep the transforms deterministic and local to the selected segment.
- Do not attempt to solve full domain realism in this ticket.
- Prefer conservative edits that are easy to inspect and test.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [x] unit tests for signal transforms
- [x] integration tests with legality and constraints
- [x] lint/static checks

### Commands
```bash
pytest -q
ruff check .
```

### Manual verification
1. Apply ShiftLevel to a plateau segment.
2. Apply SuppressSpike to a spike segment.
3. Confirm other segments are unchanged except where interpolation is explicitly intended.

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

- typed value operation module
- tests
- updated operation service wiring

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
**What changed:** `added pure signal transforms for the MVP typed value operations, added a backend value-operations service with legality and constraint feedback, and added transform plus integration tests for valid and invalid value edits`  
**Checks run:** `C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests/test_signal_transforms.py, C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests/test_value_operations.py, C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests, C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\ruff.exe check backend schemas docs`  
**Blockers:** `none`  
**Next step:** `HTS-304`

---

## 14. Completion Note

**Completed on:** `2026-03-28`  
**Summary:** `Implemented conservative typed value operations for plateau, trend, spike, and event chunks, with explicit legality checks, deterministic local signal transforms, and shared constraint feedback on edited signals.`  
**Tests passed:** `C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests/test_signal_transforms.py; C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests/test_value_operations.py; C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests; C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\ruff.exe check backend schemas docs`  
**Files changed:** `backend/app/domain/signal_transforms.py, backend/app/domain/__init__.py, backend/app/services/operations/value_ops.py, backend/app/services/operations/__init__.py, backend/app/services/__init__.py, backend/tests/test_signal_transforms.py, backend/tests/test_value_operations.py, tickets/mvp/HTS-303 - Implement MVP typed value operations on semantic chunks.md`  
**Follow-up tickets needed:** `none`
