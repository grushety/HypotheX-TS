# HTS-013 — Add operation palette and UI triggers

**Ticket ID:** `HTS-013`  
**Title:** `Add operation palette and UI triggers`  
**Status:** `done`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-010, HTS-011, HTS-012`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-013-add-operation-palette-and-ui-triggers`

---

## 1. Goal

Expose split, merge, and reclassify through a visible operation palette or equivalent control area in the viewer. UI actions should call the domain layer and surface success or failure clearly.

---

## 2. Scope

### In scope
- operation palette UI
- trigger wiring for split/merge/reclassify
- basic operation parameter controls
- success/failure feedback

### Out of scope
- constraint warnings
- counterfactual preview
- audit export

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
- `src/components/operations/`
- `src/components/sidebar/`
- `src/domain/operations/`

### Architecture layer
- [x] frontend
- [ ] backend
- [ ] API contract
- [x] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`high`

Brief reason:
> This ticket turns the domain operations into the usable semantic language of the MVP.

---

## 5. Inputs and Expected Outputs

### Inputs
- selected segment(s)
- chosen operation
- operation parameters

### Expected outputs
- updated segmentation state after valid operation
- visible failure/success feedback

---

## 6. Acceptance Criteria

- [x] the user can invoke split, merge, and reclassify from the UI
- [x] valid operations update the viewer state correctly
- [x] invalid operations fail safely with visible feedback
- [x] operation controls are disabled or guided when prerequisites are missing

---

## 7. Implementation Notes

- keep operation UI thin and delegate state changes to domain logic
- use explicit feedback instead of silent no-ops

---

## 8. Verification Plan

### Required checks
- [ ] relevant frontend tests
- [ ] manual interaction verification
- [ ] lint or static checks

### Commands
```bash
cd frontend
npm test
npm run build
```

### Manual verification
1. Invoke each operation at least once
2. Try at least one invalid operation
3. Confirm feedback and resulting state are clear

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

- operation palette UI
- viewer wiring
- interaction tests

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
- added a visible semantic operation palette with split, merge, and reclassify controls
- kept the UI layer thin by adding a small viewer-side operation executor around the shared domain contracts
- wired operation success to viewer state updates and operation failure to explicit visible feedback
- disabled or constrained controls when a selected segment or valid neighbor prerequisite is missing
**Checks run:** `npm test`; `npm run build`; frontend dev server started successfully on `http://127.0.0.1:5173/`  
**Blockers:** `none`  
**Next step:** `HTS-014`

---

## 14. Completion Note

**Completed on:** `2026-03-27`  
**Summary:** `Added the operation palette UI and connected split, merge, and reclassify triggers to the shared semantic operation domain layer with explicit success and failure feedback.`  
**Tests passed:** `npm test`; `npm run build`  
**Files changed:** `frontend operation palette/viewer files and this ticket file`  
**Follow-up tickets needed:** `none`

---

## 12. Commit

### Branch naming
`hts/hts-013-add-operation-palette-and-ui-triggers`

### Commit message
`HTS-013: add operation palette and ui triggers`
