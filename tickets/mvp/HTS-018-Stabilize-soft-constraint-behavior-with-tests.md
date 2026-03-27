# HTS-018 — Stabilize soft-constraint behavior with tests

**Ticket ID:** `HTS-018`  
**Title:** `Stabilize soft-constraint behavior with tests`  
**Status:** `done`  
**Priority:** `P1`  
**Type:** `test`  
**Depends on:** `HTS-017`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-018-stabilize-soft-constraint-behavior-with-tests`

---

## 1. Goal

Add or expand automated coverage for soft-constraint evaluation and UI behavior, and fix defects found during integration. This ticket is the stabilization gate for MVP warning behavior.

---

## 2. Scope

### In scope
- tests for pass/warn evaluation
- tests for warned UI feedback
- small bug fixes required by tests

### Out of scope
- hard constraints
- new warning categories beyond MVP scope

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `docs/planning/codex_rules_hypothe_x_ts.md`
- `docs/planning/implementation_steps_hypothe_x_ts.md`
- `docs/planning/ticket_template_codex_hypothe_x_ts.md`
- `docs/research/HypotheX-TS - Technical Plan.md`
- `docs/research/HypotheX-TS - Formal Definitions.md`

---

## 4. Affected Areas

### Likely files or modules
- `tests/domain/constraints/`
- `tests/frontend/`
- `src/domain/constraints/`
- `src/components/warnings/`

### Architecture layer
- [x] frontend
- [ ] backend
- [ ] API contract
- [x] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`medium`

Brief reason:
> Constraint behavior needs to be stable before adding audit export or more advanced models.

---

## 5. Inputs and Expected Outputs

### Inputs
- soft-constraint evaluation
- warning UI flows

### Expected outputs
- passing tests
- documented warning invariants if needed

---

## 6. Acceptance Criteria

- [x] tests cover PASS and WARN cases in both logic and UI integration
- [x] warning feedback remains attached to the correct action context
- [x] no regression is introduced in edit or operation flows
- [x] manual warned-flow smoke check remains stable

---

## 7. Implementation Notes

- focus on stabilization rather than feature expansion

---

## 8. Verification Plan

### Required checks
- [x] relevant tests
- [x] manual smoke verification

### Commands
```bash
npm test
npm run build
```

### Manual verification
1. Run warning-related tests
2. Trigger one warned edit and one warned operation

If a check cannot run, Codex must record why.

---

## 9. Definition of Done

- [x] Goal is implemented.
- [x] All acceptance criteria are satisfied.
- [x] Required tests and checks pass.
- [x] No blocking review issues remain.
- [x] Docs/comments are updated if behavior changed.
- [x] Changes are committed with the ticket ID.
- [x] Ticket status is updated to `done`.

---

## 10. Deliverables

- expanded constraint test coverage
- small fixes required by tests

---

## 11. Review Checklist

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

## 13. Status Update Block

**Current status:** `done`  
**What changed:** `Expanded soft-constraint invariant tests, added viewer warning-selection tests, extracted a small helper for choosing the active warning display context, and documented the warned-flow smoke check.`  
**Checks run:** `npm test`, `npm run build`, `frontend dev server startup log review`  
**Blockers:** `none`  
**Next step:** `Proceed to HTS-019 for audit event schema work.`

---

## 14. Completion Note

**Completed on:** `2026-03-27`  
**Summary:** `Stabilized MVP warning behavior with broader PASS/WARN coverage across constraint logic, action flows, and viewer warning-display context selection.`  
**Tests passed:** `npm test`, `npm run build`  
**Files changed:** `frontend/src/lib/constraints/evaluateSoftConstraints.test.js`, `frontend/src/lib/operations/operationFlow.integration.test.js`, `frontend/src/lib/segments/executeSegmentEditAction.test.js`, `frontend/src/lib/viewer/createViewerWarningDisplay.js`, `frontend/src/lib/viewer/createViewerWarningDisplay.test.js`, `frontend/src/views/BenchmarkViewerPage.vue`, `tickets/mvp/HTS-018-Stabilize-soft-constraint-behavior-with-tests.md`  
**Follow-up tickets needed:** `HTS-019`

---

## 12. Commit

### Branch naming
`hts/hts-018-stabilize-soft-constraint-behavior-with-tests`

### Commit message
`HTS-018: stabilize soft-constraint behavior with tests`
