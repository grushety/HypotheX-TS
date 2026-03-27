# HTS-019 — Define audit event schema and capture hooks

**Ticket ID:** `HTS-019`  
**Title:** `Define audit event schema and capture hooks`  
**Status:** `done`  
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

- [x] meaningful edits and operations generate audit events
- [x] warning outcomes are captured when present
- [x] event schema is consistent and documented enough for later export
- [x] tests cover core event creation paths

---

## 7. Implementation Notes

- prefer explicit versionable event fields over loosely structured blobs

---

## 8. Verification Plan

### Required checks
- [x] relevant unit tests
- [x] lint or static checks

### Commands
```bash
npm test
npm run build
```

### Manual verification
1. Review audit event tests for edits, operations, and warnings

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

- audit schema module
- capture hooks
- audit tests

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
**What changed:** `Added a versioned audit-event schema module, added pure event builders and append logic, wired edit and operation capture hooks into the viewer page, expanded frontend tests to include audit behavior, and documented verification in this ticket.`  
**Checks run:** `npm test`, `npm run build`, `frontend dev server startup log review`  
**Blockers:** `none`  
**Next step:** `Proceed to HTS-020 to render the interaction history panel from the captured audit events.`

---

## 14. Completion Note

**Completed on:** `2026-03-27`  
**Summary:** `Defined the first stable audit event schema and attached capture hooks for edits, operations, warnings, and rejected actions so later history/export work has a consistent event stream to build on.`  
**Tests passed:** `npm test`, `npm run build`  
**Files changed:** `frontend/src/lib/audit/auditEvents.js`, `frontend/src/lib/audit/auditEvents.test.js`, `frontend/package.json`, `frontend/src/views/BenchmarkViewerPage.vue`, `tickets/mvp/HTS-019-Define-audit-event-schema-and-capture-hooks.md`  
**Follow-up tickets needed:** `HTS-020`, `HTS-021`

---

## 12. Commit

### Branch naming
`hts/hts-019-define-audit-event-schema-and-capture-hooks`

### Commit message
`HTS-019: define audit event schema and capture hooks`
