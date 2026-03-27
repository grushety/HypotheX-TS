# HTS-009 — Create semantic operation domain layer

**Ticket ID:** `HTS-009`  
**Title:** `Create semantic operation domain layer`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-008`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-009-create-semantic-operation-domain-layer`

---

## 1. Goal

Create the domain-layer contracts and result models for semantic operations on segments. This ticket should define how split, merge, and reclassify are invoked and how success or failure is represented.

---

## 2. Scope

### In scope
- operation interfaces or service entry points
- typed or explicit result objects
- shared validation hooks for operations
- operation event payload shape for future audit use

### Out of scope
- UI palette
- actual split/merge/reclassify algorithms if separately ticketed
- preview simulation

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
- `src/domain/operations/`
- `src/lib/operations/`
- `tests/domain/`

### Architecture layer
- [ ] frontend
- [ ] backend
- [ ] API contract
- [x] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`high`

Brief reason:
> A shared domain layer prevents each operation from being implemented as a UI-specific special case.

---

## 5. Inputs and Expected Outputs

### Inputs
- selected segment(s)
- requested operation
- operation parameters

### Expected outputs
- operation result contract
- validation failure contract
- event payload structure

---

## 6. Acceptance Criteria

- [ ] operation entry points exist for split, merge, and reclassify
- [ ] success and failure are represented explicitly
- [ ] the contract is independent from any specific UI control
- [ ] unit tests cover the shared contract behavior

---

## 7. Implementation Notes

- keep the operation layer separate from rendering and side-panel concerns
- prefer clear input/output contracts

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
1. Review domain tests for operation contracts

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

- operation domain module
- contract tests
- docs note for operation result shapes

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
`hts/hts-009-create-semantic-operation-domain-layer`

### Commit message
`HTS-009: create semantic operation domain layer`
