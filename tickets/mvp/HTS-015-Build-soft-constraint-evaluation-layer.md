# HTS-015 — Build soft-constraint evaluation layer

**Ticket ID:** `HTS-015`  
**Title:** `Build soft-constraint evaluation layer`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-014`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-015-build-soft-constraint-evaluation-layer`

---

## 1. Goal

Implement the first soft-constraint evaluation layer for semantic edits and operations. The layer should return PASS or WARN with structured reasons without blocking valid-but-risky user actions.

---

## 2. Scope

### In scope
- constraint evaluation entry point
- PASS/WARN result model
- structured warning reasons
- integration points for edits and operations

### Out of scope
- hard blocking
- projected valid alternatives
- uncertainty overlays

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
- `src/domain/constraints/`
- `src/lib/constraints/`
- `tests/domain/constraints/`

### Architecture layer
- [ ] frontend
- [x] backend
- [ ] API contract
- [x] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`high`

Brief reason:
> Constraint evaluation is a key project feature and should exist as explicit logic before UI wiring.

---

## 5. Inputs and Expected Outputs

### Inputs
- proposed edit or operation
- current segment state
- constraint configuration

### Expected outputs
- PASS/WARN evaluation result
- structured warning details

---

## 6. Acceptance Criteria

- [ ] soft-constraint evaluation returns PASS or WARN explicitly
- [ ] warning reasons are structured enough for UI display
- [ ] non-violating actions are not mislabeled as warnings
- [ ] tests cover at least one pass path and one warn path

---

## 7. Implementation Notes

- keep constraints explicit and inspectable
- do not silently downgrade invalid state

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
1. Review pass and warn test scenarios

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

- constraint evaluation module
- constraint tests
- docs note for result model

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
`hts/hts-015-build-soft-constraint-evaluation-layer`

### Commit message
`HTS-015: build soft-constraint evaluation layer`
