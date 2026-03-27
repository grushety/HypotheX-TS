# HTS-021 — Export interaction log

**Ticket ID:** `HTS-021`  
**Title:** `Export interaction log`  
**Status:** `done`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-020`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-021-export-interaction-log`

---

## 1. Goal

Allow the user to export the interaction log in a stable machine-readable format. The export should include the key fields needed for later debugging and user-study analysis.

---

## 2. Scope

### In scope
- export action from the UI or command path
- stable serialized audit log format
- basic filename or download behavior
- export validation for core event fields

### Out of scope
- advanced analytics dashboards
- remote upload
- study metric computation

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
- `src/domain/audit/`
- `src/components/history/`
- `src/lib/export/`

### Architecture layer
- [x] frontend
- [x] backend
- [x] API contract
- [ ] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`medium`

Brief reason:
> Export completes the MVP auditability loop and supports later evaluation work.

---

## 5. Inputs and Expected Outputs

### Inputs
- audit event stream or store
- user export action

### Expected outputs
- serialized interaction log file or blob
- validated export payload

---

## 6. Acceptance Criteria

- [x] the user can trigger an interaction-log export
- [x] export output contains the core edit, operation, and warning fields
- [x] export format is stable and documented
- [x] tests cover at least one export path

---

## 7. Implementation Notes

- prefer a simple stable format such as JSON for the first version
- do not add remote persistence in this ticket

---

## 8. Verification Plan

### Required checks
- [x] relevant tests
- [x] manual export verification

### Commands
```bash
npm test
npm run build
```

### Manual verification
1. Perform several actions
2. Trigger export
3. Inspect the exported log for expected fields

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

- export implementation
- export tests
- docs note for export format

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
**What changed:** `Added a stable JSON export builder and filename helper, added a browser download hook, added an export action to the history panel, wired export handling into the viewer page, and added export tests.`  
**Checks run:** `npm test`, `npm run build`, `frontend dev server startup log review`  
**Blockers:** `none`  
**Next step:** `Proceed to HTS-022 for the full MVP smoke pass and docs cleanup.`

---

## 14. Completion Note

**Completed on:** `2026-03-27`  
**Summary:** `Completed the MVP auditability loop by adding JSON interaction-log export with stable filenames, serialized audit fields, and a user-triggered export action from the history panel.`  
**Tests passed:** `npm test`, `npm run build`  
**Files changed:** `frontend/src/lib/export/createInteractionLogExport.js`, `frontend/src/lib/export/createInteractionLogExport.test.js`, `frontend/src/components/history/HistoryPanel.vue`, `frontend/src/components/viewer/ViewerShell.vue`, `frontend/src/views/BenchmarkViewerPage.vue`, `frontend/src/styles.css`, `frontend/package.json`, `tickets/mvp/HTS-021-Export-interaction-log.md`  
**Follow-up tickets needed:** `HTS-022`

---

## 12. Commit

### Branch naming
`hts/hts-021-export-interaction-log`

### Commit message
`HTS-021: export interaction log`
