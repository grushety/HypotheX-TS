# HTS-011 — Implement merge operation

**Ticket ID:** `HTS-011`  
**Title:** `Implement merge operation`  
**Status:** `done`  
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

- [x] valid merge requests combine only the intended adjacent segments
- [x] invalid merge requests fail safely
- [x] unrelated segments remain unchanged
- [x] tests cover adjacency and label/compatibility edge cases if defined

---

## 7. Implementation Notes

- follow the common operation result contract from HTS-009

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
1. Review merge tests for valid and invalid cases

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

- merge operation module
- merge tests

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
- implemented the merge semantic operation inside the shared operation domain layer
- enforced adjacency and same-label compatibility before applying a merge
- returned explicit applied/rejected contracts through the shared operation result shape
- expanded operation tests to cover valid merges plus non-adjacent and incompatible-label failures
**Checks run:** `npm test`; `npm run build`  
**Blockers:** `none`  
**Next step:** `HTS-012`

---

## 14. Completion Note

**Completed on:** `2026-03-27`  
**Summary:** `Implemented merge so a valid request combines exactly two adjacent same-label segments into one merged segment and invalid requests fail with explicit contracts.`  
**Tests passed:** `npm test`; `npm run build`  
**Files changed:** `frontend operation-domain files and this ticket file`  
**Follow-up tickets needed:** `none`

---

## 12. Commit

### Branch naming
`hts/hts-011-implement-merge-operation`

### Commit message
`HTS-011: implement merge operation`
