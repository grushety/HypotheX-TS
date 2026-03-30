## Ticket Header

**Ticket ID:** `HTS-602`  
**Title:** `Prepare baseline evaluation flows and pilot telemetry validation`  
**Status:** `done`  
**Priority:** `P2`  
**Type:** `feature`  
**Depends on:** `HTS-305, HTS-404, HTS-601`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-602-baselines-pilot`

---

## 1. Goal

Prepare the first baseline evaluation flows and validate that telemetry is sufficient for a pilot user study. This ticket should connect the built system to the planned comparison conditions and confirm that the exported logs support the intended analysis.

---

## 2. Scope

### In scope
- baseline evaluation flow definition for raw manipulation or rule-only comparison
- telemetry field validation against planned study metrics
- pilot-task sample pack or scripted scenario set

### Out of scope
- full formal user study
- statistical inference over participant data
- final publication plots

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `HypotheX-TS - Research Plan.md`
- `HypotheX-TS - Evaluation.md`
- `HypotheX-TS - Research Questions.md`

---

## 4. Affected Areas

### Likely files or modules
- `evaluation/`
- `docs/`
- `tests/`

### Architecture layer
Mark all that apply:
- [x] frontend
- [x] backend
- [ ] API contract
- [ ] domain logic
- [x] model/data
- [x] tests
- [x] docs

### Risk level
`medium`

Brief reason:
> This ticket ensures the built system can actually support the study claims later, rather than only functioning as a demo.

---

## 5. Inputs and Expected Outputs

### Inputs
- session exports
- baseline interaction flow
- planned study metrics

### Expected outputs
- validated telemetry checklist
- baseline run instructions
- pilot scenario pack

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [x] A baseline flow can be executed and logged for comparison against the semantic interface.
- [x] Session exports contain the fields needed for planned interaction metrics.
- [x] A small set of pilot scenarios or tasks is documented and runnable.
- [x] Missing telemetry fields, if any, are identified explicitly rather than ignored.
- [x] The resulting note is actionable for later study preparation.

---

## 7. Implementation Notes

- This ticket is about readiness, not full study execution.
- Be honest about gaps in telemetry or baseline parity.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [x] evaluation smoke checks
- [x] docs review
- [x] manual baseline run-through

### Commands
```bash
pytest -q
ruff check .
```

### Manual verification
1. Run one semantic session and one baseline session.
2. Compare the exported logs.
3. Check whether planned metrics such as operation diversity or coverage can actually be computed.

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

- baseline evaluation notes
- telemetry validation note
- pilot scenario pack or checklist

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
**What changed:** `Added baseline-flow definitions, added telemetry-validation utilities against planned pilot metrics, added semantic and rule-only session fixtures plus a pilot scenario pack, and documented the concrete telemetry gaps that still need study-ready export fields.`  
**Checks run:** `pytest -q backend/tests; ruff check backend schemas docs model evaluation; manual pilot readiness run through evaluation/run_pilot_readiness_check.py`  
**Blockers:** `none`  
**Next step:** `Use the rule-only baseline and semantic-interface flow for internal pilot runs, then add explicit condition and task metadata before formal study collection.`

---

## 14. Completion Note

**Completed on:** `2026-03-30`  
**Summary:** `Prepared the first pilot-readiness layer by formalizing a rule-only baseline flow, validating current session exports against planned interaction metrics, documenting three runnable pilot scenarios, and surfacing the remaining telemetry gaps instead of hiding them. Current exports support session duration, operation diversity, constraint feedback, suggestion uptake, and target-segment coverage; they still lack explicit condition, participant, and task markers.`  
**Tests passed:** `pytest -q backend/tests; ruff check backend schemas docs model evaluation; manual pilot readiness run returned SCENARIO_COUNT=3, SEMANTIC_MISSING_CHECKS=3, BASELINE_MISSING_CHECKS=4, with semantic-only event coverage ['suggestion_accepted'] and shared event coverage ['operation_applied']`  
**Files changed:** `evaluation/baselines.py; evaluation/telemetry.py; evaluation/pilot_readiness.py; evaluation/run_pilot_readiness_check.py; evaluation/pilot-scenarios.json; evaluation/fixtures/semantic-session.json; evaluation/fixtures/rule-only-baseline-session.json; evaluation/README.md; evaluation/__init__.py; backend/tests/test_pilot_readiness.py; docs/pilot-readiness-note.md`  
**Follow-up tickets needed:** `none`
