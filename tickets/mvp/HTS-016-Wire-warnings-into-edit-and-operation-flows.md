# HTS-016 — Wire warnings into edit and operation flows

**Ticket ID:** `HTS-016`  
**Title:** `Wire warnings into edit and operation flows`  
**Status:** `done`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-015`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-016-wire-warnings-into-edit-and-operation-flows`

---

## 1. Goal

Call the soft-constraint layer during manual edits and semantic operations and attach the resulting PASS/WARN status to the action outcome. This ticket should not block actions that only warn.

---

## 2. Scope

### In scope
- constraint checks on relevant edits
- constraint checks on split/merge/reclassify
- result propagation to UI state
- no blocking on WARN-only cases

### Out of scope
- hard blocking
- projected alternatives
- full audit export

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
- `src/domain/constraints/`
- `src/domain/operations/`
- `src/components/viewer/`
- `src/components/operations/`

### Architecture layer
- [x] frontend
- [x] backend
- [ ] API contract
- [x] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`high`

Brief reason:
> This integrates constraint reasoning into the actual MVP interaction loop.

---

## 5. Inputs and Expected Outputs

### Inputs
- edit or operation request
- constraint evaluation result

### Expected outputs
- action result with PASS/WARN status
- warning-ready UI state

---

## 6. Acceptance Criteria

- [x] warnings are evaluated during relevant edit and operation flows
- [x] WARN does not block otherwise allowed actions
- [x] PASS/WARN status is attached consistently across supported actions
- [x] tests cover at least one warned action and one clean action

---

## 7. Implementation Notes

- reuse a common action-result shape where possible
- do not let warnings mutate underlying domain state

---

## 8. Verification Plan

### Required checks
- [x] relevant tests
- [x] manual interaction verification

### Commands
```bash
npm test
npm run build
```

### Manual verification
1. Trigger one warned action
2. Trigger one clean action
3. Confirm both still behave correctly

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

- constraint wiring across flows
- tests for warned vs clean actions

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
**What changed:** `Added a shared edit-action executor, attached soft-constraint results to edit and operation action outcomes, propagated warning-ready state through the page flow, expanded tests for PASS and WARN paths, and documented verification in this ticket.`  
**Checks run:** `npm test`, `npm run build`, `frontend dev server startup log review`  
**Blockers:** `none`  
**Next step:** `Proceed to HTS-017 to render warning UI and explanations.`

---

## 14. Completion Note

**Completed on:** `2026-03-27`  
**Summary:** `Wired soft-constraint evaluation into manual edits and semantic operations so successful actions now carry PASS/WARN results and warning payloads without turning WARN cases into blockers.`  
**Tests passed:** `npm test`, `npm run build`  
**Files changed:** `frontend/src/lib/segments/executeSegmentEditAction.js`, `frontend/src/lib/segments/executeSegmentEditAction.test.js`, `frontend/src/lib/operations/executeOperationAction.js`, `frontend/src/lib/operations/executeOperationAction.test.js`, `frontend/src/lib/operations/operationFlow.integration.test.js`, `frontend/src/views/BenchmarkViewerPage.vue`, `tickets/mvp/HTS-016-Wire-warnings-into-edit-and-operation-flows.md`  
**Follow-up tickets needed:** `HTS-017`, `HTS-018`

---

## 12. Commit

### Branch naming
`hts/hts-016-wire-warnings-into-edit-and-operation-flows`

### Commit message
`HTS-016: wire warnings into edit and operation flows`
