## Ticket Header

**Ticket ID:** `HTS-504`  
**Title:** `Implement guarded prototype updates and duration smoothing rules`  
**Status:** `done`  
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

- [x] Prototype updates can be gated by confidence or equivalent policy.
- [x] Prototype state does not grow without bound.
- [x] Too-short segments can be merged or smoothed by rule-based duration logic.
- [x] Tests cover at least one drift-protection case and one too-short-segment smoothing case.
- [x] The ticket does not introduce full HSMM complexity.

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
- [x] model/service tests
- [x] lint/static checks

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

- [x] Goal is implemented.
- [x] All acceptance criteria are satisfied.
- [x] Required tests and checks pass.
- [x] No blocking review issues remain.
- [x] Docs/comments are updated if behavior changed.
- [x] Changes are committed with the ticket ID.
- [x] Ticket status is updated to `done`.

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
**What changed:** `Added bounded prototype-memory helpers with confidence and drift gates, added duration smoothing for too-short provisional segments, and documented the stabilization heuristics without changing the suggestion API contract.`  
**Checks run:** `pytest -q backend/tests/test_prototype_classifier.py backend/tests/test_boundary_suggestions.py backend/tests/test_suggestion_stabilization.py; pytest -q backend/tests; ruff check backend schemas docs model; manual stabilization check for low-confidence rejection, drift rejection, and short-event smoothing`  
**Blockers:** `none`  
**Next step:** `Move to HTS-505 for evaluation-facing suggestion diagnostics or the next scheduled suggestion-model ticket.`

---

## 14. Completion Note

**Completed on:** `2026-03-30`  
**Summary:** `Implemented explicit prototype stabilization for the MVP suggestion model through confidence-gated updates, bounded per-label memory, drift-based freeze logic, and a rule-based duration smoother that merges obviously too-short provisional segments into the more compatible neighbor.`  
**Tests passed:** `pytest -q backend/tests/test_prototype_classifier.py backend/tests/test_boundary_suggestions.py backend/tests/test_suggestion_stabilization.py; pytest -q backend/tests; ruff check backend schemas docs model; manual stabilization check returned LOW_CONF_APPLIED=False, HIGH_DRIFT_APPLIED=False, and SMOOTHED_SEGMENTS=[('plateau', 0, 7), ('trend', 8, 13)]`  
**Files changed:** `backend/app/services/suggestion/prototype_classifier.py; backend/app/services/suggestion/__init__.py; backend/app/services/suggestions.py; backend/tests/test_suggestion_stabilization.py; model/suggestion/prototype_classifier.py; model/suggestion/__init__.py; docs/suggestion-stabilization-note.md`  
**Follow-up tickets needed:** `none`
