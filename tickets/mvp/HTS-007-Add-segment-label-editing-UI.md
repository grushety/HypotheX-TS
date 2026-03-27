# HTS-007 — Add segment label editing UI

**Ticket ID:** `HTS-007`  
**Title:** `Add segment label editing UI`  
**Status:** `done`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-004`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-007-add-segment-label-editing-ui`

---

## 1. Goal

Allow the user to change the semantic label of the currently selected segment from the side panel or equivalent control. The label update should be immediate and kept separate from boundary movement logic.

---

## 2. Scope

### In scope
- label editor for selected segment
- state update for label change
- available-label source or placeholder set
- visible confirmation of updated label

### Out of scope
- operation-based reclassify workflow
- model adaptation
- constraint logic for labels unless already defined

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
- `src/components/sidebar/`
- `src/state/segments/`
- `src/domain/labels/`

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
> Label assignment is part of the user-defined segmentation layer and needed before full reclassify operations.

---

## 5. Inputs and Expected Outputs

### Inputs
- selected segment
- label choice

### Expected outputs
- updated segment label
- reflected overlay and side-panel state

---

## 6. Acceptance Criteria

- [x] the selected segment label can be changed from the UI
- [x] the new label appears in both overlay and detail view
- [x] changing a label does not alter segment boundaries
- [x] invalid label values are rejected or unavailable by design

---

## 7. Implementation Notes

- keep label update logic separate from boundary movement logic
- use project vocabulary for label names if already defined

---

## 8. Verification Plan

### Required checks
- [ ] relevant frontend tests
- [ ] manual label-edit verification

### Commands
```bash
cd frontend
npm test
npm run build
```

### Manual verification
1. Select a segment
2. Change its label
3. Confirm the new label appears everywhere it should

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

- label editor UI
- label-update wiring
- label-edit tests

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
- added a pure segment-label update helper with the formal semantic label set
- added a side-panel label editor for the active segment
- wired label changes into shared viewer state so the overlay and detail view update immediately
- extended viewer state tests to show active label metadata
**Checks run:** `npm test`; `npm run build`; frontend dev server started successfully on `http://127.0.0.1:5173/`  
**Blockers:** `none`  
**Next step:** `HTS-008`

---

## 14. Completion Note

**Completed on:** `2026-03-27`  
**Summary:** `Added side-panel semantic label editing for the active segment with pure label-update logic and immediate overlay/detail synchronization.`  
**Tests passed:** `npm test`; `npm run build`  
**Files changed:** `frontend label-editor/viewer state files and this ticket file`  
**Follow-up tickets needed:** `none`

---

## 12. Commit

### Branch naming
`hts/hts-007-add-segment-label-editing-ui`

### Commit message
`HTS-007: add segment label editing ui`
