# HTS-022 — Run MVP smoke pass and docs cleanup

**Ticket ID:** `HTS-022`  
**Title:** `Run MVP smoke pass and docs cleanup`  
**Status:** `done`  
**Priority:** `P1`  
**Type:** `test`  
**Depends on:** `HTS-021`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-022-run-mvp-smoke-pass-and-docs-cleanup`

---

## 1. Goal

Run an end-to-end MVP smoke pass across viewer, editing, operations, warnings, and audit export, then clean up developer-facing docs to reflect the implemented workflow. This ticket is the release gate for the first ticket set.

---

## 2. Scope

### In scope
- manual MVP smoke checklist
- small fixes found during smoke pass
- docs cleanup for implemented MVP workflow

### Out of scope
- new MVP features
- benchmark expansion
- advanced study instrumentation

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `docs/planning/codex_rules_hypothe_x_ts.md`
- `docs/planning/implementation_steps_hypothe_x_ts.md`
- `docs/planning/ticket_template_codex_hypothe_x_ts.md`
- `docs/research/HypotheX-TS - Technical Plan.md`
- `docs/research/HypotheX-TS - Formal Definitions.md`
- `tickets/mvp/`

---

## 4. Affected Areas

### Likely files or modules
- `docs/`
- `tickets/mvp/`
- `tests/`
- `src/`

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
> This ticket closes the first MVP loop and documents what is actually implemented.

---

## 5. Inputs and Expected Outputs

### Inputs
- implemented MVP capabilities from HTS-001 to HTS-021

### Expected outputs
- smoke-tested MVP
- updated docs reflecting actual workflow

---

## 6. Acceptance Criteria

- [x] the full MVP flow can be executed without blocking defects
- [x] docs reflect the implemented viewer, editing, operations, warnings, and audit export behavior
- [x] open issues found during smoke pass are either fixed or recorded explicitly
- [x] the MVP ticket set is ready for the next planning pass

---

## 7. Implementation Notes

- keep this ticket focused on validation and documentation, not feature growth

---

## 8. Verification Plan

### Required checks
- [x] manual smoke verification
- [x] relevant automated regression tests

### Commands
```bash
npm test
npm run build
```

### Manual verification
1. Load a benchmark series
2. Select and edit a segment
3. Run split, merge, and reclassify
4. Trigger a warned action
5. Review history and export the log

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

- smoke checklist results
- small fixes required by smoke pass
- updated docs or notes

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
**What changed:** `Ran the MVP regression gate, updated outdated frontend hero copy, cleaned up README to reflect the actual MVP workflow, fixed the history separator rendering artifact, and recorded the remaining environment-specific smoke limitation.`  
**Checks run:** `npm test`, `npm run build`, `frontend dev server startup log review on http://127.0.0.1:5176`, `attempted frontend-plus-backend smoke check`  
**Blockers:** `Backend-linked smoke check remains environment-blocked because python is not runnable via Start-Process on this machine.`  
**Next step:** `Use this MVP baseline for the next planning pass or broader product direction changes.`

---

## 14. Completion Note

**Completed on:** `2026-03-27`  
**Summary:** `Closed the first MVP ticket set by re-running the frontend regression gate, confirming runtime startup, and updating developer-facing docs so they match the implemented viewer, warning, history, and export workflow.`  
**Tests passed:** `npm test`, `npm run build`  
**Files changed:** `README.md`, `frontend/src/components/history/HistoryPanel.vue`, `frontend/src/views/BenchmarkViewerPage.vue`, `tickets/mvp/HTS-022-Run-MVP-smoke-pass-and-docs-cleanup.md`  
**Follow-up tickets needed:** `none in this ticket set; next work should come from a new planning pass`

---

## 12. Commit

### Branch naming
`hts/hts-022-run-mvp-smoke-pass-and-docs-cleanup`

### Commit message
`HTS-022: run mvp smoke pass and docs cleanup`
