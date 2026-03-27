# HTS-018 — Stabilize soft-constraint behavior with tests

**Ticket ID:** `HTS-018`  
**Title:** `Stabilize soft-constraint behavior with tests`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `test`  
**Depends on:** `HTS-017`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-018-stabilize-soft-constraint-behavior-with-tests`

---

## 1. Goal

Add or expand automated coverage for soft-constraint evaluation and UI behavior, and fix defects found during integration. This ticket is the stabilization gate for MVP warning behavior.

---

## 2. Scope

### In scope
- tests for pass/warn evaluation
- tests for warned UI feedback
- small bug fixes required by tests

### Out of scope
- hard constraints
- new warning categories beyond MVP scope

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
- `tests/domain/constraints/`
- `tests/frontend/`
- `src/domain/constraints/`
- `src/components/warnings/`

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
> Constraint behavior needs to be stable before adding audit export or more advanced models.

---

## 5. Inputs and Expected Outputs

### Inputs
- soft-constraint evaluation
- warning UI flows

### Expected outputs
- passing tests
- documented warning invariants if needed

---

## 6. Acceptance Criteria

- [ ] tests cover PASS and WARN cases in both logic and UI integration
- [ ] warning feedback remains attached to the correct action context
- [ ] no regression is introduced in edit or operation flows
- [ ] manual warned-flow smoke check remains stable

---

## 7. Implementation Notes

- focus on stabilization rather than feature expansion

---

## 8. Verification Plan

### Required checks
- [ ] relevant tests
- [ ] manual smoke verification

### Commands
```bash
# fill with repo-specific commands
```

### Manual verification
1. Run warning-related tests
2. Trigger one warned edit and one warned operation

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

- expanded constraint test coverage
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
`hts/hts-018-stabilize-soft-constraint-behavior-with-tests`

### Commit message
`HTS-018: stabilize soft-constraint behavior with tests`
