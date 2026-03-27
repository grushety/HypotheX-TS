# HTS-022 — Run MVP smoke pass and docs cleanup

**Ticket ID:** `HTS-022`  
**Title:** `Run MVP smoke pass and docs cleanup`  
**Status:** `todo`  
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

- [ ] the full MVP flow can be executed without blocking defects
- [ ] docs reflect the implemented viewer, editing, operations, warnings, and audit export behavior
- [ ] open issues found during smoke pass are either fixed or recorded explicitly
- [ ] the MVP ticket set is ready for the next planning pass

---

## 7. Implementation Notes

- keep this ticket focused on validation and documentation, not feature growth

---

## 8. Verification Plan

### Required checks
- [ ] manual smoke verification
- [ ] relevant automated regression tests

### Commands
```bash
# fill with repo-specific commands
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

- [ ] Goal is implemented.
- [ ] All acceptance criteria are satisfied.
- [ ] Required tests and checks pass.
- [ ] No blocking review issues remain.
- [ ] Docs/comments are updated if behavior changed.
- [ ] Changes are committed with the ticket ID.
- [ ] Ticket status is updated to `done`.

---

## 10. Deliverables

- smoke checklist results
- small fixes required by smoke pass
- updated docs or notes

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
`hts/hts-022-run-mvp-smoke-pass-and-docs-cleanup`

### Commit message
`HTS-022: run mvp smoke pass and docs cleanup`
