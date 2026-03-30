## Ticket Header

**Ticket ID:** `HTS-601`  
**Title:** `Build technical evaluation harness and metric pipeline`  
**Status:** `done`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-203, HTS-204, HTS-504`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-601-evaluation-harness`

---

## 1. Goal

Create the technical evaluation harness for segmentation quality, stability, and constraint-awareness. This ticket should make it possible to run reproducible evaluations over datasets or fixtures rather than relying on demo behavior alone.

---

## 2. Scope

### In scope
- dataset split/loading utilities for evaluation
- metric implementations or wrappers for IoU, Boundary F1, Covering, and WARI/SMS where feasible
- metrics for over-segmentation, prototype drift, and constraint violation rate

### Out of scope
- full user-study analysis
- dashboard visualizations
- publication-quality figures for every metric

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `HypotheX-TS - Evaluation.md`
- `HypotheX-TS - Research Plan.md`
- `MyPaper-HypotheX-TS - ML Model Approach - Revised.md`

---

## 4. Affected Areas

### Likely files or modules
- `evaluation/`
- `tests/`
- `docs/`

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
`high`

Brief reason:
> Without this harness, the system cannot support defensible technical claims or informed simplification decisions.

---

## 5. Inputs and Expected Outputs

### Inputs
- ground-truth segmentations
- predicted segmentations
- audit/session logs
- constraint results

### Expected outputs
- metric tables or serializable reports
- reproducible evaluation scripts

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [x] Technical evaluation can be run on at least one fixture or dataset split.
- [x] IoU and Boundary F1 are computed reproducibly.
- [x] At least one stability metric and one constraint metric are reported.
- [x] Results can be exported in a machine-readable form.
- [x] Evaluation code is separated from application runtime logic.

---

## 7. Implementation Notes

- Start with the metrics most directly tied to the research questions.
- Document any approximation or unavailable metric explicitly.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [x] evaluation tests or fixture checks
- [x] lint/static checks

### Commands
```bash
pytest -q
ruff check .
```

### Manual verification
1. Run the evaluation on one known-good and one known-bad segmentation example.
2. Inspect the metric outputs for plausibility.
3. Confirm reports are saved in a reusable format.

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

- evaluation scripts
- metric modules
- basic reports
- docs note on running evaluation

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
**What changed:** `Added a standalone evaluation package with fixture loading, reproducible segmentation/stability/constraint metrics, a CLI runner, machine-readable JSON report export, and known-good/known-bad evaluation fixtures.`  
**Checks run:** `pytest -q backend/tests; ruff check backend schemas docs model evaluation; manual evaluation runs for known-good and known-bad fixtures through evaluation/run_fixture_evaluation.py`  
**Blockers:** `none`  
**Next step:** `Move to HTS-602 for baseline evaluation flow preparation and telemetry validation.`

---

## 14. Completion Note

**Completed on:** `2026-03-30`  
**Summary:** `Built the first technical evaluation harness under evaluation/, with fixture-driven case loading, reproducible macro IoU, Boundary F1, Covering, over-segmentation, prototype-drift, and constraint-violation metrics, plus a CLI that exports JSON reports for known-good and known-bad examples. WARI and SMS are left explicitly unsupported in this MVP harness rather than approximated silently.`  
**Tests passed:** `pytest -q backend/tests; ruff check backend schemas docs model evaluation; manual good fixture run produced macroIoU=1.0, boundaryF1=1.0, constraintViolationRate=0.0; manual bad fixture run produced macroIoU=0.266667, boundaryF1=0.571429, constraintViolationRate=1.0`  
**Files changed:** `evaluation/__init__.py; evaluation/io.py; evaluation/metrics.py; evaluation/harness.py; evaluation/run_fixture_evaluation.py; evaluation/fixtures/known-good.json; evaluation/fixtures/known-bad.json; evaluation/README.md; backend/tests/test_evaluation_harness.py`  
**Follow-up tickets needed:** `none`
