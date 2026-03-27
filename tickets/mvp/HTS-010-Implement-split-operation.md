# HTS-010 — Implement split operation

**Ticket ID:** `HTS-010`  
**Title:** `Implement split operation`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-009`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-010-implement-split-operation`

---

## 1. Goal

Implement the split semantic operation for a selected segment. The result should produce two valid segments with consistent ordering, labels, and boundary rules.

---

## 2. Scope

### In scope
- split algorithm on a selected segment
- validation of split location
- resulting two-segment state
- failure result for invalid splits

### Out of scope
- UI trigger
- merge or reclassify logic
- counterfactual preview

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
- `src/domain/operations/split.*`
- `tests/domain/operations/`

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
> Split is a core semantic operation and a direct test of segment-centered editing semantics.

---

## 5. Inputs and Expected Outputs

### Inputs
- selected segment
- split point or equivalent split parameter

### Expected outputs
- updated segment list with two resulting segments
- explicit invalid-split result

---

## 6. Acceptance Criteria

- [ ] valid split requests produce exactly two resulting segments from the original one
- [ ] invalid split requests fail safely
- [ ] segment ordering and boundary validity are preserved
- [ ] tests cover edge cases such as boundary-near splits

---

## 7. Implementation Notes

- keep split logic pure and independent from UI affordances

---

## 8. Verification Plan

### Required checks
- [ ] relevant unit tests

### Commands
```bash
# fill with repo-specific commands
```

### Manual verification
1. Review split tests for valid and invalid cases

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

- split operation module
- split tests

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
`hts/hts-010-implement-split-operation`

### Commit message
`HTS-010: implement split operation`
