# HTS-011 — Implement merge operation

**Ticket ID:** `HTS-011`  
**Title:** `Implement merge operation`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-010`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-011-implement-merge-operation`

---

## 1. Goal

Implement the merge semantic operation for adjacent compatible segments. The result should create one valid merged segment and preserve the rest of the sequence unchanged.

---

## 2. Scope

### In scope
- merge algorithm for adjacent segments
- validation of adjacency and compatibility
- resulting merged segment state
- failure result for invalid merges

### Out of scope
- UI trigger
- reclassify logic
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
- `src/domain/operations/merge.*`
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
> Merge complements split and is required for the minimal semantic operation language.

---

## 5. Inputs and Expected Outputs

### Inputs
- two adjacent segments
- merge request

### Expected outputs
- updated segment list with one merged segment
- explicit invalid-merge result

---

## 6. Acceptance Criteria

- [ ] valid merge requests combine only the intended adjacent segments
- [ ] invalid merge requests fail safely
- [ ] unrelated segments remain unchanged
- [ ] tests cover adjacency and label/compatibility edge cases if defined

---

## 7. Implementation Notes

- follow the common operation result contract from HTS-009

---

## 8. Verification Plan

### Required checks
- [ ] relevant unit tests

### Commands
```bash
# fill with repo-specific commands
```

### Manual verification
1. Review merge tests for valid and invalid cases

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

- merge operation module
- merge tests

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
`hts/hts-011-implement-merge-operation`

### Commit message
`HTS-011: implement merge operation`
