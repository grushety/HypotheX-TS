## Ticket Header

**Ticket ID:** `HTS-501`  
**Title:** `Integrate boundary proposal module for suggestion model v1`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-201`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-501-boundary-proposer`

---

## 1. Goal

Integrate the first boundary proposal mechanism for the suggestion model so the system can suggest candidate segment boundaries. The MVP should favor a conservative and inspectable approach, such as ClaSP or an equivalent change-point proposer, before a learned boundary head is introduced.

---

## 2. Scope

### In scope
- boundary proposer integration
- conversion of boundary scores into provisional segments
- suggestion payload fields for candidate boundaries

### Out of scope
- learned boundary head training
- full label classification
- online adaptation

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `MyPaper-HypotheX-TS - ML Model Approach - Revised.md`
- `HypotheX-TS - Technical Plan.md`
- `HypotheX-TS - Evaluation.md`

---

## 4. Affected Areas

### Likely files or modules
- `model/`
- `backend/services/suggestion/`
- `tests/`

### Architecture layer
Mark all that apply:
- [ ] frontend
- [x] backend
- [x] API contract
- [ ] domain logic
- [x] model/data
- [x] tests
- [ ] docs

### Risk level
`medium`

Brief reason:
> A bad boundary proposer will create over-segmentation or miss obvious state changes. However, starting with a conservative proposer keeps the model layer explainable.

---

## 5. Inputs and Expected Outputs

### Inputs
- time series payload
- boundary proposer config

### Expected outputs
- candidate boundaries
- optional boundary scores/confidence
- provisional segment list

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [ ] The system can generate candidate boundaries for a sample series.
- [ ] Boundary proposals are serializable into the suggestion payload.
- [ ] The proposer can be configured without touching UI code.
- [ ] At least one test covers a series with obvious change points.
- [ ] The module can be swapped later without changing the external suggestion contract.

---

## 7. Implementation Notes

- Keep the integration thin and modular.
- Do not add a second learned boundary pathway under this ticket.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [ ] model/service tests
- [ ] lint/static checks

### Commands
```bash
pytest -q
ruff check .
```

### Manual verification
1. Run the proposer on a clear multi-regime sample series.
2. Inspect the candidate boundaries.
3. Confirm the payload is consumable by the backend/UI.

If a check cannot run, Codex must record why.

---

## 9. Definition of Done

A ticket is done only when all items below are true.

- [ ] Goal is implemented.
- [ ] All acceptance criteria are satisfied.
- [ ] Required tests and checks pass.
- [ ] No blocking review issues remain.
- [ ] Docs/comments are updated if behavior changed.
- [ ] Changes are committed with the ticket ID.
- [ ] Ticket status is updated to `done`.

---

## 10. Deliverables

- boundary proposer integration
- tests
- config wiring

---

## 11. Review Checklist

Before marking complete, verify:

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
`{t['branch']}`

### Commit message
`{tid}: {t['title'][0].lower()+t['title'][1:]}`

---

## 13. Status Update Block

**Current status:** `todo`  
**What changed:** `none yet`  
**Checks run:** `none yet`  
**Blockers:** `none`  
**Next step:** `{t['status_next']}`

---

## 14. Completion Note

**Completed on:** `<date>`  
**Summary:** `<brief summary of implemented result>`  
**Tests passed:** `<list>`  
**Files changed:** `<list or summary>`  
**Follow-up tickets needed:** `<IDs or none>`
