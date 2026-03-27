# HTS-006 — Add boundary drag interaction in the viewer

**Ticket ID:** `HTS-006`  
**Title:** `Add boundary drag interaction in the viewer`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-005`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-006-add-boundary-drag-interaction-in-the-viewer`

---

## 1. Goal

Connect the viewer overlay to the boundary edit domain logic so a user can drag a shared boundary between adjacent segments. The UI should update immediately on valid edits and reject invalid moves cleanly.

---

## 2. Scope

### In scope
- drag handles or equivalent boundary interaction
- wiring to boundary edit logic
- live UI update after valid edit
- visible invalid-edit feedback

### Out of scope
- label editing
- semantic operations
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
- `src/components/viewer/SegmentationOverlay.*`
- `src/components/viewer/BoundaryHandle.*`
- `src/domain/segments/`

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
> This is the first editable semantic interaction and a major MVP capability.

---

## 5. Inputs and Expected Outputs

### Inputs
- selected or hoverable shared boundary
- drag action
- boundary edit logic result

### Expected outputs
- updated overlay after valid move
- warning/error feedback after invalid move

---

## 6. Acceptance Criteria

- [ ] a user can drag a valid shared boundary and see the overlay update
- [ ] invalid moves are rejected cleanly and leave state consistent
- [ ] only adjacent segments change after a valid move
- [ ] the interaction is covered by frontend or integration tests where feasible

---

## 7. Implementation Notes

- reuse HTS-005 logic rather than duplicating calculations in the UI
- keep visual feedback explicit

---

## 8. Verification Plan

### Required checks
- [ ] relevant frontend tests
- [ ] manual drag verification
- [ ] lint or static checks

### Commands
```bash
# fill with repo-specific commands
```

### Manual verification
1. Drag a valid boundary left and right
2. Attempt an invalid move
3. Confirm only adjacent segments changed

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

- boundary drag UI
- viewer wiring
- interaction tests

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
`hts/hts-006-add-boundary-drag-interaction-in-the-viewer`

### Commit message
`HTS-006: add boundary drag interaction in the viewer`
