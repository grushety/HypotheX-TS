## Ticket Header

**Ticket ID:** `HTS-304`  
**Title:** `Add constraint feedback API contract for operation results`  
**Status:** `done`  
**Priority:** `P0`  
**Type:** `feature`  
**Depends on:** `HTS-206, HTS-302, HTS-303`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-304-constraint-feedback-api`

---

## 1. Goal

Create a stable API response contract for operation outcomes so the frontend can consistently render PASS, WARN, and FAIL states. This ticket should standardize how violations, severity, and user-readable messages are returned after any attempted edit.

---

## 2. Scope

### In scope
- operation result envelope
- violation payload structure
- consistent mapping of pass/warn/fail states

### Out of scope
- frontend rendering
- advanced projection algorithms
- analytics dashboards

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `TICKET-TEMPLATE-CODEX.md`
- `HypotheX-TS - Technical Plan.md`
- `HypotheX-TS - Evaluation.md`

---

## 4. Affected Areas

### Likely files or modules
- `backend/api/contracts.py`
- `backend/api/routes/`
- `schemas/`
- `tests/`

### Architecture layer
Mark all that apply:
- [ ] frontend
- [x] backend
- [x] API contract
- [ ] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`medium`

Brief reason:
> If result shapes drift per route or operation, the frontend will become fragile and later logging will be inconsistent.

---

## 5. Inputs and Expected Outputs

### Inputs
- attempted operation request
- constraint engine result
- updated or unchanged state

### Expected outputs
- standardized JSON response with status and violation details

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [x] All operation endpoints or service responses use one standardized result shape.
- [x] The payload distinguishes PASS, WARN, FAIL, and includes violation details when relevant.
- [x] A failed operation can return state-preserving feedback without partial mutation.
- [x] Contract tests or schema validation cover representative success and failure cases.
- [x] The response shape is documented for frontend consumers.

---

## 7. Implementation Notes

- Keep the contract stable and explicit.
- Do not leak backend exception traces into API responses.
- Human-readable messages should coexist with machine-readable codes.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [x] API contract validation
- [x] integration tests for representative operation results
- [x] lint/static checks

### Commands
```bash
pytest -q
ruff check .
```

### Manual verification
1. Trigger one PASS response.
2. Trigger one WARN response.
3. Trigger one FAIL response and inspect the payload fields.

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

- standard result contract
- route/service integration
- tests
- contract docs note

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
**What changed:** `added one shared operation-result envelope across structural and value operations, added the shared schema and sample fixture, and added representative PASS/WARN/FAIL contract tests plus updated operation-service tests to assert the normalized payload`  
**Checks run:** `C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests/test_structural_operations.py backend/tests/test_value_operations.py backend/tests/test_operation_result_contract.py, C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests, C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\ruff.exe check backend schemas docs`  
**Blockers:** `ticket references HypotheX-TS - Evaluation.md, but no file with that name exists in docs/research/; the ticket was completed using the existing technical-plan and shared-contract context instead`  
**Next step:** `HTS-305`

---

## 14. Completion Note

**Completed on:** `2026-03-29`  
**Summary:** `Standardized structural and value operation outcomes on a single PASS/WARN/FAIL contract with explicit applied state, machine-readable reason codes, top-level violations, and shared schema documentation for frontend consumers.`  
**Tests passed:** `C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests/test_structural_operations.py backend/tests/test_value_operations.py backend/tests/test_operation_result_contract.py; C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests; C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\ruff.exe check backend schemas docs`  
**Files changed:** `backend/app/schemas/operation_results.py, backend/app/schemas/__init__.py, backend/app/services/operations/structural.py, backend/app/services/operations/value_ops.py, backend/app/services/operations/__init__.py, backend/tests/test_structural_operations.py, backend/tests/test_value_operations.py, backend/tests/test_operation_result_contract.py, schemas/operation-result.schema.json, schemas/fixtures/operation-result.sample.json, schemas/contract-index.json, schemas/README.md, tickets/mvp/HTS-304 - Add constraint feedback API contract for operation results.md`  
**Follow-up tickets needed:** `none`
