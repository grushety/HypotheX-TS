## Ticket Header

**Ticket ID:** `HTS-501`  
**Title:** `Integrate boundary proposal module for suggestion model v1`  
**Status:** `done`  
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

- [x] The system can generate candidate boundaries for a sample series.
- [x] Boundary proposals are serializable into the suggestion payload.
- [x] The proposer can be configured without touching UI code.
- [x] At least one test covers a series with obvious change points.
- [x] The module can be swapped later without changing the external suggestion contract.

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
- [x] model/service tests
- [x] lint/static checks

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

- [x] Goal is implemented.
- [x] All acceptance criteria are satisfied.
- [x] Required tests and checks pass.
- [x] No blocking review issues remain.
- [x] Docs/comments are updated if behavior changed.
- [x] Changes are committed with the ticket ID.
- [x] Ticket status is updated to `done`.

---

## 10. Deliverables

- boundary proposer integration
- tests
- config wiring

---

## 11. Review Checklist

Before marking complete, verify:

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

## 12. Commit

### Branch naming
`{t['branch']}`

### Commit message
`{tid}: {t['title'][0].lower()+t['title'][1:]}`

---

## 13. Status Update Block

**Current status:** `done`  
**What changed:** `Added a conservative change-point boundary proposer, a thin backend suggestion service, and a shared suggestion-proposal contract/fixture so boundary candidates and provisional segments can be serialized consistently before label classification is added.`  
**Checks run:** `pytest -q backend/tests/test_boundary_suggestions.py; pytest -q backend/tests; ruff check backend schemas docs model; manual proposer run on a clear three-regime series`  
**Blockers:** `none`  
**Next step:** `Move to HTS-502 for segment encoding and prototype chunk classification.`

---

## 14. Completion Note

**Completed on:** `2026-03-30`  
**Summary:** `Integrated a conservative, inspectable boundary proposer for suggestion model v1, converted boundary candidates into provisional segments, and established a stable suggestion payload contract that can later absorb label proposals without changing the external wire shape.`  
**Tests passed:** `pytest -q backend/tests/test_boundary_suggestions.py; pytest -q backend/tests; ruff check backend schemas docs model; manual proposer run produced boundaries at 12 and 24 for a three-regime series and a matching provisional segment list.`  
**Files changed:** `backend/app/services/suggestion/; backend/app/services/suggestions.py; backend/app/schemas/suggestions.py; backend/tests/test_boundary_suggestions.py; model/suggestion/; schemas/suggestion-proposal.schema.json; schemas/fixtures/suggestion-proposal.sample.json; schemas/contract-index.json; schemas/README.md`  
**Follow-up tickets needed:** `none`
