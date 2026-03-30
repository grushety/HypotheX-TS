## Ticket Header

**Ticket ID:** `HTS-503`  
**Title:** `Expose suggestion API and accept-override workflow`  
**Status:** `done`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-501, HTS-502, HTS-304, HTS-403`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-503-suggestion-workflow`

---

## 1. Goal

Connect the suggestion model to the application so users can inspect model-proposed segments, accept them, or override them through manual edits. This ticket turns the model from a background experiment into an assistive part of the interaction loop.

---

## 2. Scope

### In scope
- suggestion API contract from backend to frontend
- accept suggestion action
- override suggestion action with audit hooks

### Out of scope
- online model retraining
- advanced disagreement analytics
- duration smoothing

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `MyPaper-HypotheX-TS - ML Model Approach - Revised.md`
- `HypotheX-TS - Technical Plan.md`
- `HypotheX-TS - Research Questions.md`

---

## 4. Affected Areas

### Likely files or modules
- `backend/services/suggestion/`
- `backend/api/routes/`
- `frontend/src/`
- `tests/`

### Architecture layer
Mark all that apply:
- [x] frontend
- [x] backend
- [x] API contract
- [ ] domain logic
- [x] model/data
- [x] tests
- [ ] docs

### Risk level
`medium`

Brief reason:
> The assistive model is only useful if acceptance and override flows are explicit and logged consistently.

---

## 5. Inputs and Expected Outputs

### Inputs
- model suggestion payload
- user accept/override action
- current segmentation state

### Expected outputs
- applied suggestion state
- override state transition
- logged accept/override events

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [x] Users can request and view model suggestions.
- [x] Users can accept a suggested segmentation or edit over it without losing control.
- [x] Accept and override actions are distinguishable in the audit log.
- [x] The frontend uses the suggestion API rather than ad hoc mock logic.
- [x] Tests cover at least one accept and one override flow.

---

## 7. Implementation Notes

- Keep the user authoritative.
- Do not silently auto-apply model changes.
- Logging consistency matters as much as UI behavior here.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [x] integration tests across backend/frontend boundary
- [x] lint/static checks
- [x] manual verification

### Commands
```bash
pytest -q
ruff check .
npm run lint
npm run build
```

### Manual verification
1. Load a sample suggestion.
2. Accept it.
3. Reload and perform an override instead.
4. Inspect the resulting log entries.

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

- suggestion API wiring
- frontend accept/override flow
- tests

---

## 11. Review Checklist

Before marking complete, verify:

### Scope review
- [x] No unrelated files were changed.
- [x] No out-of-scope behavior was added.

### Architecture review
- [x] Business logic is not in route handlers.
- [x] Domain logic is not embedded in UI code.
- [x] Layer boundaries remain clean.

### Quality review
- [x] Names match project concepts.
- [x] Error handling is explicit.
- [x] New behavior is covered by tests.
- [x] Logging/audit behavior is preserved where relevant.

### Contract review
- [x] Public interfaces remain compatible, or the change is documented in the ticket.

---

## 12. Commit

### Branch naming
`{t['branch']}`

### Commit message
`{tid}: {t['title'][0].lower()+t['title'][1:]}`

---

## 13. Status Update Block

**Current status:** `done`  
**What changed:** `Added a real backend suggestion endpoint, added a POST route for suggestion accept/override audit decisions, and replaced the frontend's cloned proposal baseline with actual suggestion fetch, explicit accept/override controls, automatic override logging on subsequent manual edits, and session-log/export support for suggestion decisions.`  
**Checks run:** `pytest -q backend/tests; ruff check backend schemas docs model; npm test -- --runInBand; npm run lint; npm run build; frontend dev-server smoke pass on http://127.0.0.1:5173; manual backend route walkthrough for suggestion load + accept + override + session export`  
**Blockers:** `none`  
**Next step:** `Move to HTS-504 for guarded prototype updates and duration smoothing rules.`

---

## 14. Completion Note

**Completed on:** `2026-03-30`  
**Summary:** `Connected the suggestion model to the app through a real benchmark suggestion API, frontend suggestion loading and comparison controls, explicit suggestion acceptance, and explicit or automatic override logging. Accept and override decisions are now distinguishable in both the backend audit session stream and the frontend session history/export path.`  
**Tests passed:** `pytest -q backend/tests; ruff check backend schemas docs model; npm test -- --runInBand; npm run lint; npm run build; frontend dev-server smoke pass on http://127.0.0.1:5173; manual route walkthrough returned suggestion status 200, accept status 201, override status 201, and exported events suggestion_accepted,suggestion_overridden.`  
**Files changed:** `backend/app/routes/audit.py; backend/app/routes/benchmarks.py; backend/app/services/suggestion/prototype_classifier.py; backend/app/services/suggestion/__init__.py; backend/tests/test_audit_log.py; backend/tests/test_benchmark_routes.py; frontend/src/views/BenchmarkViewerPage.vue; frontend/src/services/api/benchmarkApi.js; frontend/src/services/api/benchmarkApi.test.js; frontend/src/lib/viewer/createProposalSegments.js; frontend/src/lib/viewer/createProposalSegments.test.js; frontend/src/lib/viewer/createModelComparisonState.js; frontend/src/lib/viewer/createModelComparisonState.test.js; frontend/src/lib/audit/auditEvents.js; frontend/src/lib/audit/createHistoryEntries.js; frontend/src/lib/export/createInteractionLogExport.js; frontend/src/components/comparison/ModelComparisonPanel.vue; frontend/src/components/viewer/ViewerShell.vue; frontend/src/styles.css`  
**Follow-up tickets needed:** `none`
