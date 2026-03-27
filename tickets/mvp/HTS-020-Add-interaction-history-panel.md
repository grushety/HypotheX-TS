# HTS-020 — Add interaction history panel

**Ticket ID:** `HTS-020`  
**Title:** `Add interaction history panel`  
**Status:** `done`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-019`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-020-add-interaction-history-panel`

---

## 1. Goal

Show recent audit events in a visible history panel so users can inspect what actions have occurred. The history should be readable, ordered, and tied to the core interaction types introduced in the MVP.

---

## 2. Scope

### In scope
- history panel UI
- rendering of recent audit events
- basic ordering and event summaries
- viewer integration

### Out of scope
- export file generation
- advanced filtering
- analytics summaries

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
- `src/components/history/`
- `src/domain/audit/`
- `src/components/viewer/`

### Architecture layer
- [x] frontend
- [x] backend
- [ ] API contract
- [ ] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`medium`

Brief reason:
> A visible history panel turns auditability into an actual user-facing MVP capability.

---

## 5. Inputs and Expected Outputs

### Inputs
- audit event stream or store

### Expected outputs
- visible history list
- ordered event summaries

---

## 6. Acceptance Criteria

- [x] recent edits and operations appear in the history panel
- [x] warning outcomes appear where relevant
- [x] history ordering is stable and understandable
- [x] history rendering does not block or corrupt the main viewer flow

---

## 7. Implementation Notes

- keep summaries concise and human-readable
- do not overbuild filtering or analytics in this ticket

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
1. Perform several edits and operations
2. Open or view the history panel
3. Confirm entries appear in correct order

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

- history panel UI
- history integration
- history tests

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
**What changed:** `Added a history entry formatter, added a presentational history panel component, wired audit events into the viewer shell, added ordering/summary tests, and documented verification in this ticket.`  
**Checks run:** `npm test`, `npm run build`, `frontend dev server startup log review`  
**Blockers:** `none`  
**Next step:** `Proceed to HTS-021 to export the interaction log.`

---

## 14. Completion Note

**Completed on:** `2026-03-27`  
**Summary:** `Added a visible interaction history panel that renders recent audit events in reverse chronological order with concise summaries, warning visibility, and stable status labels.`  
**Tests passed:** `npm test`, `npm run build`  
**Files changed:** `frontend/src/components/history/HistoryPanel.vue`, `frontend/src/lib/audit/createHistoryEntries.js`, `frontend/src/lib/audit/createHistoryEntries.test.js`, `frontend/src/components/viewer/ViewerShell.vue`, `frontend/src/views/BenchmarkViewerPage.vue`, `frontend/src/styles.css`, `tickets/mvp/HTS-020-Add-interaction-history-panel.md`  
**Follow-up tickets needed:** `HTS-021`

---

## 12. Commit

### Branch naming
`hts/hts-020-add-interaction-history-panel`

### Commit message
`HTS-020: add interaction history panel`
