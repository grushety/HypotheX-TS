## Ticket Header

**Ticket ID:** `HTS-504`  
**Title:** `Implement guarded prototype updates and duration smoothing rules`  
**Status:** `todo`  
**Priority:** `P2`  
**Type:** `feature`  
**Depends on:** `HTS-502, HTS-503`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-504-prototype-guards`

---

## 1. Goal

Stabilize the first assistive model by adding guarded prototype updates and simple duration smoothing rules. This ticket should reduce obvious model drift and over-segmentation without introducing full online fine-tuning or HSMM complexity.

---

## 2. Scope

### In scope
- confidence-gated prototype updates
- capped prototype memory buffer or recomputation strategy
- simple class-specific minimum-duration smoothing or merge rules

### Out of scope
- full HSMM
- end-to-end online retraining
- operation-aware loss design

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `MyPaper-HypotheX-TS - ML Model Approach - Revised.md`
- `HypotheX-TS - Evaluation.md`
- `HypotheX-TS - Research Questions.md`

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
- [ ] API contract
- [ ] domain logic
- [x] model/data
- [x] tests
- [x] docs

### Risk level
`medium`

Brief reason:
> This ticket directly addresses the main MVP risks of prototype drift and jittery over-segmentation.

---

## 5. Inputs and Expected Outputs

### Inputs
- new validated segment examples
- current prototype memory
- candidate segment sequence

### Expected outputs
- stabilized prototype updates
- smoothed segment sequence
- drift or update metadata

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [ ] Prototype updates can be gated by confidence or equivalent policy.
- [ ] Prototype state does not grow without bound.
- [ ] Too-short segments can be merged or smoothed by rule-based duration logic.
- [ ] Tests cover at least one drift-protection case and one too-short-segment smoothing case.
- [ ] The ticket does not introduce full HSMM complexity.

---

## 7. Implementation Notes

- Keep the stabilization heuristics explicit and easy to ablate later.
- Document update thresholds clearly.

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
1. Apply several mock corrections to the same class.
2. Inspect whether prototypes remain stable.
3. Run smoothing on a segmentation with jittery short segments.

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

- guarded prototype update logic
- duration smoothing rules
- tests
- docs note on stabilization heuristics

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
