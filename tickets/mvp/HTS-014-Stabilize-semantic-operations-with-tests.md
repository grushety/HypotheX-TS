# HTS-014 — Stabilize semantic operations with tests

**Ticket ID:** `HTS-014`  
**Title:** `Stabilize semantic operations with tests`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `test`  
**Depends on:** `HTS-013`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-014-stabilize-semantic-operations-with-tests`

---

## 1. Goal

Expand automated coverage and fix defects across split, merge, and reclassify after UI integration. This ticket is the stabilization gate for the MVP operation language.

---

## 2. Scope

### In scope
- integration-level tests for operations
- edge-case tests for operation failures
- small bug fixes required by tests

### Out of scope
- new features beyond split/merge/reclassify
- constraints engine
- audit export

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
- `tests/domain/operations/`
- `tests/frontend/`
- `src/domain/operations/`
- `src/components/operations/`

### Architecture layer
- [x] frontend
- [ ] backend
- [ ] API contract
- [x] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`medium`

Brief reason:
> Operation correctness should be stabilized before adding constraints and logging.

---

## 5. Inputs and Expected Outputs

### Inputs
- operation flows from UI to domain layer
- failure cases

### Expected outputs
- passing tests
- documented operation invariants if needed

---

## 6. Acceptance Criteria

- [ ] automated tests cover successful split, merge, and reclassify flows
- [ ] automated tests cover at least one invalid case for each operation
- [ ] no regression is introduced in selection or editing behavior
- [ ] manual end-to-end operation flow remains stable

---

## 7. Implementation Notes

- do not expand feature scope; focus on stability and correctness

---

## 8. Verification Plan

### Required checks
- [ ] relevant unit tests
- [ ] integration or component tests
- [ ] manual smoke verification

### Commands
```bash
# fill with repo-specific commands
```

### Manual verification
1. Run all operation-related tests
2. Perform one end-to-end pass through the operation palette

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

- expanded operation test suite
- small fixes required by tests

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
`hts/hts-014-stabilize-semantic-operations-with-tests`

### Commit message
`HTS-014: stabilize semantic operations with tests`
