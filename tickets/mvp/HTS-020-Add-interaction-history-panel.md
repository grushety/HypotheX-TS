# HTS-020 — Add interaction history panel

**Ticket ID:** `HTS-020`  
**Title:** `Add interaction history panel`  
**Status:** `todo`  
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

- [ ] recent edits and operations appear in the history panel
- [ ] warning outcomes appear where relevant
- [ ] history ordering is stable and understandable
- [ ] history rendering does not block or corrupt the main viewer flow

---

## 7. Implementation Notes

- keep summaries concise and human-readable
- do not overbuild filtering or analytics in this ticket

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
1. Perform several edits and operations
2. Open or view the history panel
3. Confirm entries appear in correct order

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

- history panel UI
- history integration
- history tests

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
`hts/hts-020-add-interaction-history-panel`

### Commit message
`HTS-020: add interaction history panel`
