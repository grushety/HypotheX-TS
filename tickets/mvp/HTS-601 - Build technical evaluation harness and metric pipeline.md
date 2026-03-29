## Ticket Header

**Ticket ID:** `HTS-601`  
**Title:** `Build technical evaluation harness and metric pipeline`  
**Status:** `todo`  
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

- [ ] Technical evaluation can be run on at least one fixture or dataset split.
- [ ] IoU and Boundary F1 are computed reproducibly.
- [ ] At least one stability metric and one constraint metric are reported.
- [ ] Results can be exported in a machine-readable form.
- [ ] Evaluation code is separated from application runtime logic.

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
- [ ] evaluation tests or fixture checks
- [ ] lint/static checks

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

- [ ] Goal is implemented.
- [ ] All acceptance criteria are satisfied.
- [ ] Required tests and checks pass.
- [ ] No blocking review issues remain.
- [ ] Docs/comments are updated if behavior changed.
- [ ] Changes are committed with the ticket ID.
- [ ] Ticket status is updated to `done`.

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
