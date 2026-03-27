# HTS-017 — Add warning UI and explanations

**Ticket ID:** `HTS-017`  
**Title:** `Add warning UI and explanations`  
**Status:** `done`  
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

- [x] warning UI appears for WARN cases
- [x] warning UI does not appear for PASS cases unless explicitly designed
- [x] warning text is tied to the action that triggered it
- [x] warning state updates cleanly after subsequent actions

---

## 7. Implementation Notes

- keep FAIL semantics reserved for later hard-constraint work
- prefer concise but specific explanations

---

## 8. Verification Plan

### Required checks
- [x] relevant frontend tests
- [x] manual UI verification

### Commands
```bash
npm test
npm run build
```

### Manual verification
1. Trigger a warned action
2. Trigger a PASS action
3. Confirm the warning UI updates correctly

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

- warning UI components
- viewer integration
- warning tests

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
**What changed:** `Added a dedicated warning panel component, added a viewer-side warning display model, wired warning display state into the viewer shell, cleared stale warning state after subsequent actions, and added warning display tests.`  
**Checks run:** `npm test`, `npm run build`, `frontend dev server startup log review`  
**Blockers:** `none`  
**Next step:** `Proceed to HTS-018 to stabilize warning behavior with additional tests.`

---

## 14. Completion Note

**Completed on:** `2026-03-27`  
**Summary:** `Added warning UI that renders only for WARN outcomes, ties explanations to the triggering action, and updates cleanly after later PASS or failed actions.`  
**Tests passed:** `npm test`, `npm run build`  
**Files changed:** `frontend/src/components/warnings/WarningPanel.vue`, `frontend/src/components/viewer/ViewerShell.vue`, `frontend/src/lib/viewer/createWarningDisplayModel.js`, `frontend/src/lib/viewer/createWarningDisplayModel.test.js`, `frontend/src/views/BenchmarkViewerPage.vue`, `frontend/src/styles.css`, `tickets/mvp/HTS-017-Add-warning-UI-and-explanations.md`  
**Follow-up tickets needed:** `HTS-018`

---

## 12. Commit

### Branch naming
`hts/hts-017-add-warning-ui-and-explanations`

### Commit message
`HTS-017: add warning ui and explanations`
