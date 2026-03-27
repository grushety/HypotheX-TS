# HTS-021 — Export interaction log

**Ticket ID:** `HTS-021`  
**Title:** `Export interaction log`  
**Status:** `todo`  
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

- [ ] the user can trigger an interaction-log export
- [ ] export output contains the core edit, operation, and warning fields
- [ ] export format is stable and documented
- [ ] tests cover at least one export path

---

## 7. Implementation Notes

- prefer a simple stable format such as JSON for the first version
- do not add remote persistence in this ticket

---

## 8. Verification Plan

### Required checks
- [ ] relevant tests
- [ ] manual export verification

### Commands
```bash
# fill with repo-specific commands
```

### Manual verification
1. Perform several actions
2. Trigger export
3. Inspect the exported log for expected fields

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

- export implementation
- export tests
- docs note for export format

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
`hts/hts-021-export-interaction-log`

### Commit message
`HTS-021: export interaction log`
