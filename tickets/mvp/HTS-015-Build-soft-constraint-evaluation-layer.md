# HTS-015 — Build soft-constraint evaluation layer

**Ticket ID:** `HTS-015`  
**Title:** `Build soft-constraint evaluation layer`  
**Status:** `done`  
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

- [x] soft-constraint evaluation returns PASS or WARN explicitly
- [x] warning reasons are structured enough for UI display
- [x] non-violating actions are not mislabeled as warnings
- [x] tests cover at least one pass path and one warn path

---

## 7. Implementation Notes

- keep constraints explicit and inspectable
- do not silently downgrade invalid state

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
1. Review pass and warn test scenarios

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

- constraint evaluation module
- constraint tests
- docs note for result model

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
**What changed:** `Added a pure soft-constraint evaluator with PASS/WARN output, added edit/operation entry points, added pass/warn tests, updated frontend test command, documented verification in this ticket.`  
**Checks run:** `npm test`, `npm run build`  
**Blockers:** `none`  
**Next step:** `Proceed to HTS-016 to wire warning results into edit and operation flows.`

---

## 14. Completion Note

**Completed on:** `2026-03-27`  
**Summary:** `Built the first soft-constraint evaluation layer as a frontend domain module with explicit PASS/WARN results and structured warning payloads for edit and operation contexts.`  
**Tests passed:** `npm test`, `npm run build`  
**Files changed:** `frontend/src/lib/constraints/evaluateSoftConstraints.js`, `frontend/src/lib/constraints/evaluateSoftConstraints.test.js`, `frontend/package.json`, `tickets/mvp/HTS-015-Build-soft-constraint-evaluation-layer.md`  
**Follow-up tickets needed:** `HTS-016`, `HTS-017`, `HTS-018`

---

## 12. Commit

### Branch naming
`hts/hts-015-build-soft-constraint-evaluation-layer`

### Commit message
`HTS-015: build soft-constraint evaluation layer`
