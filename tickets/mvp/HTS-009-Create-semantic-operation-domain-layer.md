# HTS-009 — Create semantic operation domain layer

**Ticket ID:** `HTS-009`  
**Title:** `Create semantic operation domain layer`  
**Status:** `done`  
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

- [x] operation entry points exist for split, merge, and reclassify
- [x] success and failure are represented explicitly
- [x] the contract is independent from any specific UI control
- [x] unit tests cover the shared contract behavior

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
cd frontend
npm test
npm run build
```

### Manual verification
1. Review domain tests for operation contracts

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

- operation domain module
- contract tests
- docs note for operation result shapes

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
- added a UI-independent semantic operation contract module with split, merge, and reclassify entry points
- added explicit request validation, explicit success/failure result shapes, and audit-ready event payloads
- added shared operation dispatch and not-implemented failure contracts for later algorithm tickets
- extended the frontend test command to include operation domain tests
**Checks run:** `npm test`; `npm run build`  
**Blockers:** `none`  
**Next step:** `HTS-010`

---

## 14. Completion Note

**Completed on:** `2026-03-27`  
**Summary:** `Created the semantic operation domain layer with explicit contracts, shared validation, dispatch entry points, and contract tests for split, merge, and reclassify.`  
**Tests passed:** `npm test`; `npm run build`  
**Files changed:** `frontend operation-domain files, frontend test script, and this ticket file`  
**Follow-up tickets needed:** `none`

---

## 12. Commit

### Branch naming
`hts/hts-009-create-semantic-operation-domain-layer`

### Commit message
`HTS-009: create semantic operation domain layer`
