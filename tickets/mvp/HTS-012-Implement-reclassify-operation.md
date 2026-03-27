# HTS-012 — Implement reclassify operation

**Ticket ID:** `HTS-012`  
**Title:** `Implement reclassify operation`  
**Status:** `done`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-009`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-012-implement-reclassify-operation`

---

## 1. Goal

Implement the reclassify semantic operation as an explicit operation-layer action, even though the UI already supports direct label editing. This ticket establishes reclassify as part of the formal operation language.

---

## 2. Scope

### In scope
- reclassify operation in domain layer
- validation of target labels
- operation result and event payload
- state update behavior consistent with label semantics

### Out of scope
- UI palette
- preview simulation
- model adaptation

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
- `src/domain/operations/reclassify.*`
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
`medium`

Brief reason:
> Reclassify belongs in the explicit operation language and not only in ad hoc label editing controls.

---

## 5. Inputs and Expected Outputs

### Inputs
- selected segment
- target label

### Expected outputs
- updated segment label via operation layer
- invalid-target-label result if applicable

---

## 6. Acceptance Criteria

- [x] reclassify updates only the intended segment label
- [x] the operation follows the shared success/failure contract
- [x] direct label editing and operation-based reclassify do not create inconsistent state
- [x] tests cover valid and invalid target labels if applicable

---

## 7. Implementation Notes

- reuse existing label semantics where possible
- do not duplicate label dictionaries across modules

---

## 8. Verification Plan

### Required checks
- [ ] relevant unit tests

### Commands
```bash
cd frontend
npm test
npm run build
```

### Manual verification
1. Review reclassify tests

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

- reclassify operation module
- reclassify tests

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
**What changed:** 
- implemented the reclassify semantic operation inside the shared operation domain layer
- reused the existing pure label-update semantics instead of duplicating label dictionaries or update logic
- returned explicit applied/rejected contracts through the shared operation result shape
- expanded operation tests to cover valid reclassify behavior and missing-segment failures
**Checks run:** `npm test`; `npm run build`  
**Blockers:** `none`  
**Next step:** `HTS-013`

---

## 14. Completion Note

**Completed on:** `2026-03-27`  
**Summary:** `Implemented reclassify so the operation layer updates exactly one segment label through the shared label semantics and returns explicit success or failure contracts.`  
**Tests passed:** `npm test`; `npm run build`  
**Files changed:** `frontend operation-domain files and this ticket file`  
**Follow-up tickets needed:** `none`

---

## 12. Commit

### Branch naming
`hts/hts-012-implement-reclassify-operation`

### Commit message
`HTS-012: implement reclassify operation`
