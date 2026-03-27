# HTS-008 — Add edit-state validation and tests

**Ticket ID:** `HTS-008`  
**Title:** `Add edit-state validation and tests`  
**Status:** `done`  
**Priority:** `P1`  
**Type:** `test`  
**Depends on:** `HTS-006, HTS-007`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-008-add-edit-state-validation-and-tests`

---

## 1. Goal

Consolidate validation behavior for manual edits and add tests that cover boundary moves, label changes, and invalid edit paths. This ticket hardens the first editable semantic layer before later operations are added.

---

## 2. Scope

### In scope
- validation scenarios for manual edits
- test coverage for valid boundary edits
- test coverage for invalid boundary edits
- test coverage for label editing

### Out of scope
- new semantic operations
- constraints engine
- model-driven suggestions

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
- `tests/domain/`
- `tests/frontend/`
- `src/domain/segments/`
- `src/state/`

### Architecture layer
- [ ] frontend
- [ ] backend
- [ ] API contract
- [x] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`medium`

Brief reason:
> This ticket is a stabilization gate before the system adds more complex operations.

---

## 5. Inputs and Expected Outputs

### Inputs
- boundary edit behavior
- label edit behavior
- invalid edit cases

### Expected outputs
- passing validation tests
- documented edit invariants if needed

---

## 6. Acceptance Criteria

- [x] tests cover accepted and rejected boundary edits
- [x] tests cover label updates and invalid label handling if applicable
- [x] no regression is introduced in segment selection or overlay rendering
- [x] manual edit flow remains stable after test-backed fixes

---

## 7. Implementation Notes

- focus on validation and stabilization rather than new features

---

## 8. Verification Plan

### Required checks
- [ ] relevant unit tests
- [ ] integration or component tests
- [ ] manual smoke check

### Commands
```bash
cd frontend
npm test
npm run build
```

### Manual verification
1. Run all edit-related tests
2. Repeat a manual boundary and label edit flow

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

- expanded test suite
- small fixes required to satisfy tests
- updated notes on edit invariants if needed

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
**What changed:** 
- added a shared editable-segment validator for contiguity, coverage, and supported labels
- hardened boundary and label edit helpers to validate both input and resulting segment state
- added expanded unit coverage for invalid edit state plus an integration-style manual edit flow test
- confirmed overlay and selection state remain stable after boundary and label edits
**Checks run:** `npm test`; `npm run build`; frontend dev server started successfully on `http://127.0.0.1:5173/`  
**Blockers:** `none`  
**Next step:** `HTS-009`

---

## 14. Completion Note

**Completed on:** `2026-03-27`  
**Summary:** `Consolidated edit-state validation, expanded the manual-edit test suite, and verified boundary edits, label edits, selection retention, and overlay stability together.`  
**Tests passed:** `npm test`; `npm run build`  
**Files changed:** `frontend segment validation/test files and this ticket file`  
**Follow-up tickets needed:** `none`

---

## 12. Commit

### Branch naming
`hts/hts-008-add-edit-state-validation-and-tests`

### Commit message
`HTS-008: add edit-state validation and tests`
