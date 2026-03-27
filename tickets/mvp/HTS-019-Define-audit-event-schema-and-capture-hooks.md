# HTS-019 — Define audit event schema and capture hooks

**Ticket ID:** `HTS-019`  
**Title:** `Define audit event schema and capture hooks`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-018`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-019-define-audit-event-schema-and-capture-hooks`

---

## 1. Goal

Define the structured audit event schema for meaningful user actions and add capture hooks for manual edits, semantic operations, and warning outcomes. This should create a stable event model for later UI history and export.

---

## 2. Scope

### In scope
- audit event schema
- capture hooks for edits
- capture hooks for operations
- capture hooks for warning outcomes

### Out of scope
- history panel UI
- export file generation
- analytics dashboards

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
- `src/lib/audit/`
- `tests/domain/audit/`

### Architecture layer
- [ ] frontend
- [x] backend
- [x] API contract
- [x] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`high`

Brief reason:
> Auditability is a core product feature and should start from a clean event schema.

---

## 5. Inputs and Expected Outputs

### Inputs
- edit action outcome
- operation action outcome
- warning status and details

### Expected outputs
- structured audit event stream or store
- documented audit event shape

---

## 6. Acceptance Criteria

- [ ] meaningful edits and operations generate audit events
- [ ] warning outcomes are captured when present
- [ ] event schema is consistent and documented enough for later export
- [ ] tests cover core event creation paths

---

## 7. Implementation Notes

- prefer explicit versionable event fields over loosely structured blobs

---

## 8. Verification Plan

### Required checks
- [ ] relevant unit tests
- [ ] lint or static checks

### Commands
```bash
# fill with repo-specific commands
```

### Manual verification
1. Review audit event tests for edits, operations, and warnings

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

- audit schema module
- capture hooks
- audit tests

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
`hts/hts-019-define-audit-event-schema-and-capture-hooks`

### Commit message
`HTS-019: define audit event schema and capture hooks`
