## Ticket Header

**Ticket ID:** `HTS-305`  
**Title:** `Implement audit logging and session export`  
**Status:** `done`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-301, HTS-304`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-305-audit-logging`

---

## 1. Goal

Implement persistent audit logging for user and model actions so sessions can be exported for debugging, evaluation, and later user-study analysis. This ticket should capture operation type, timestamps, before/after state summaries, constraint outcomes, and whether model suggestions were accepted or overridden.

---

## 2. Scope

### In scope
- audit log entry schema and storage
- session export endpoint or utility
- core events for operations and suggestion accept/override actions

### Out of scope
- full analytics dashboard
- frontend history panel rendering
- statistical analysis scripts

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `HypotheX-TS - Evaluation.md`
- `HypotheX-TS - Research Plan.md`
- `MyPaper-HypotheX-TS - ML Model Approach - Revised.md`

---

## 4. Affected Areas

### Likely files or modules
- `backend/services/audit_log.py`
- `schemas/`
- `backend/api/routes/`
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
> Without clean logging, the later study metrics and debugging loop will be compromised. Retroactively adding missing fields will be painful.

---

## 5. Inputs and Expected Outputs

### Inputs
- operation result
- state transition metadata
- model suggestion event

### Expected outputs
- stored audit log entries
- session export file or payload

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [x] Every successful or rejected operation creates a log entry.
- [x] Log entries include timestamps, action type, affected segment IDs or boundaries, and constraint outcomes.
- [x] Model suggestion accept/override actions are distinguishable from manual edits.
- [x] Session export returns a complete ordered action history.
- [x] Tests verify at least one successful and one failed operation are logged correctly.

---

## 7. Implementation Notes

- Keep storage format simple and export-friendly.
- Do not bury important fields inside opaque text blobs.
- Favor stable identifiers for segments or actions where possible.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [x] unit tests for logging
- [x] integration tests for export
- [x] lint/static checks

### Commands
```bash
pytest -q
ruff check .
```

### Manual verification
1. Perform a few edits.
2. Export the session.
3. Confirm the action sequence is complete and readable.

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

- audit logging service
- session export path
- tests
- log schema updates

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
**What changed:** `added persistent audit session/event storage, added a session export API route, extended the session-log and typed-operation shared schemas for value operations and suggestion decisions, and added backend audit/export tests`  
**Checks run:** `C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests/test_audit_log.py, C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests, C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\ruff.exe check backend schemas docs`  
**Blockers:** `ticket references HypotheX-TS - Evaluation.md and HypotheX-TS - Research Plan.md, but no files with those exact names exist under docs/research/; the ticket was completed using the available technical-plan, ML-model, and shared-schema context instead`  
**Next step:** `HTS-401`

---

## 14. Completion Note

**Completed on:** `2026-03-29`  
**Summary:** `Implemented a SQLite-backed audit log for operation and suggestion-decision events, added session export through a backend API route, and aligned the shared session-log contract with ordered export-ready audit payloads.`  
**Tests passed:** `C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests/test_audit_log.py; C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\pytest.exe -q backend/tests; C:\Users\yulia\PycharmProjects\HypotheX-TS\.venv\Scripts\ruff.exe check backend schemas docs`  
**Files changed:** `backend/app/models/audit_log.py, backend/app/models/__init__.py, backend/app/services/audit_log.py, backend/app/services/__init__.py, backend/app/routes/audit.py, backend/app/factory.py, backend/tests/test_audit_log.py, schemas/session-log.schema.json, schemas/fixtures/session-log.sample.json, schemas/typed-operation.schema.json, schemas/README.md, tickets/mvp/HTS-305 - Implement audit logging and session export.md`  
**Follow-up tickets needed:** `none`
