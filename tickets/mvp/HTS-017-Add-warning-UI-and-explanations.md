# HTS-017 — Add warning UI and explanations

**Ticket ID:** `HTS-017`  
**Title:** `Add warning UI and explanations`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-016`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-017-add-warning-ui-and-explanations`

---

## 1. Goal

Display soft-constraint warnings in the viewer so users can see when an edit or operation is allowed but potentially problematic. Warnings should be tied to the triggered action and clearly distinguish WARN from FAIL.

---

## 2. Scope

### In scope
- warning banner, panel, or inline status UI
- warning explanation rendering
- visual distinction between PASS/WARN and future FAIL states
- clearing or updating warning state after new actions

### Out of scope
- hard-blocking UI
- projected alternatives
- uncertainty visualization

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
- `src/components/warnings/`
- `src/components/viewer/`
- `src/components/operations/`

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
> Constraint visibility is part of the project’s user-facing design, not just internal logic.

---

## 5. Inputs and Expected Outputs

### Inputs
- PASS/WARN status
- warning explanation payload

### Expected outputs
- visible warning UI
- updated action feedback state

---

## 6. Acceptance Criteria

- [ ] warning UI appears for WARN cases
- [ ] warning UI does not appear for PASS cases unless explicitly designed
- [ ] warning text is tied to the action that triggered it
- [ ] warning state updates cleanly after subsequent actions

---

## 7. Implementation Notes

- keep FAIL semantics reserved for later hard-constraint work
- prefer concise but specific explanations

---

## 8. Verification Plan

### Required checks
- [ ] relevant frontend tests
- [ ] manual UI verification

### Commands
```bash
# fill with repo-specific commands
```

### Manual verification
1. Trigger a warned action
2. Trigger a PASS action
3. Confirm the warning UI updates correctly

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

- warning UI components
- viewer integration
- warning tests

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
`hts/hts-017-add-warning-ui-and-explanations`

### Commit message
`HTS-017: add warning ui and explanations`
