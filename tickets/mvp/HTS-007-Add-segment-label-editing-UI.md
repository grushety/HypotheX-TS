# HTS-007 — Add segment label editing UI

**Ticket ID:** `HTS-007`  
**Title:** `Add segment label editing UI`  
**Status:** `todo`  
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

- [ ] the selected segment label can be changed from the UI
- [ ] the new label appears in both overlay and detail view
- [ ] changing a label does not alter segment boundaries
- [ ] invalid label values are rejected or unavailable by design

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
# fill with repo-specific commands
```

### Manual verification
1. Select a segment
2. Change its label
3. Confirm the new label appears everywhere it should

If a check cannot run, Codex must record why.

---

## 9. Definition of Done

- [ ] Goal is implemented.
- [ ] All acceptance criteria are satisfied.
- [ ] Required tests and checks pass.
- [ ] No blocking review issues remain.
- [ ] Docs/comments are updated if behavior changed.
- [ ] Changes are committed with the ticket ID.
- [ ] Ticket status is updated to `done`.

---

## 10. Deliverables

- label editor UI
- label-update wiring
- label-edit tests

---

## 11. Review Checklist

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
`hts/hts-007-add-segment-label-editing-ui`

### Commit message
`HTS-007: add segment label editing ui`
