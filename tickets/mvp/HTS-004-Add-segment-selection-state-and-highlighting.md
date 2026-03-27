# HTS-004 — Add segment selection state and highlighting

**Ticket ID:** `HTS-004`  
**Title:** `Add segment selection state and highlighting`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-003`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-004-add-segment-selection-state-and-highlighting`

---

## 1. Goal

Allow the user to select a segment in the overlay and reflect that selection consistently in UI state and visual highlighting. This creates the base selection model required by editing and operations tickets.

---

## 2. Scope

### In scope
- click or equivalent selection for a segment
- selected-segment state
- visual highlight for the active segment
- side-panel reflection of selected segment metadata

### Out of scope
- boundary drag editing
- operations palette actions
- audit logging

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
- `src/state/`
- `src/components/sidebar/`

### Architecture layer
- [x] frontend
- [ ] backend
- [ ] API contract
- [ ] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`medium`

Brief reason:
> Selection is the first interactive state transition on top of the semantic layer.

---

## 5. Inputs and Expected Outputs

### Inputs
- rendered segment overlay
- user selection action

### Expected outputs
- selected segment state
- highlighted segment
- side-panel metadata

---

## 6. Acceptance Criteria

- [ ] clicking a segment updates selected state predictably
- [ ] only one segment is active at a time unless a later ticket changes this rule
- [ ] the active segment is visually highlighted
- [ ] selection state survives harmless rerenders

---

## 7. Implementation Notes

- keep selection state explicit and centralized enough for later reuse
- do not embed future operation behavior in this ticket

---

## 8. Verification Plan

### Required checks
- [ ] relevant frontend tests
- [ ] manual interaction verification

### Commands
```bash
# fill with repo-specific commands
```

### Manual verification
1. Select several segments one after another
2. Verify highlight moves correctly
3. Confirm side panel shows the active segment metadata

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

- selection state implementation
- highlighting UI
- selection tests

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
`hts/hts-004-add-segment-selection-state-and-highlighting`

### Commit message
`HTS-004: add segment selection state and highlighting`
