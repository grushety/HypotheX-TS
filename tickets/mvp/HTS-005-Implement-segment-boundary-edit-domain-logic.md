# HTS-005 — Implement segment boundary edit domain logic

**Ticket ID:** `HTS-005`  
**Title:** `Implement segment boundary edit domain logic`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-004`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-005-implement-segment-boundary-edit-domain-logic`

---

## 1. Goal

Create the domain logic that updates two adjacent segments when a shared boundary moves. This ticket should define valid moves, invalid moves, and the resulting normalized segment state.

---

## 2. Scope

### In scope
- pure boundary-update function or service
- validation of adjacent segment updates
- state normalization after valid edits
- clear error result for invalid edits

### Out of scope
- UI drag interaction
- label editing UI
- model adaptation
- audit logging

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
- `src/domain/segments/`
- `src/lib/segments/`
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
> This is the core correctness layer for manual boundary editing and should exist before UI drag behavior.

---

## 5. Inputs and Expected Outputs

### Inputs
- existing ordered segment list
- requested boundary move
- series length or bounds

### Expected outputs
- updated normalized segment list
- explicit invalid-edit result

---

## 6. Acceptance Criteria

- [ ] moving a shared boundary updates only the two adjacent segments
- [ ] invalid moves are rejected without corrupting state
- [ ] segment ordering and non-overlap constraints remain valid after accepted edits
- [ ] the logic is covered by unit tests for happy path and edge cases

---

## 7. Implementation Notes

- keep this logic pure and UI-independent
- prefer explicit result objects over silent mutation failures

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
1. Review unit test output for valid and invalid boundary moves

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

- boundary edit domain module
- unit tests for valid/invalid edits
- docs note for boundary rules

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
`hts/hts-005-implement-segment-boundary-edit-domain-logic`

### Commit message
`HTS-005: implement segment boundary edit domain logic`
