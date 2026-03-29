## Ticket Header

**Ticket ID:** `HTS-602`  
**Title:** `Prepare baseline evaluation flows and pilot telemetry validation`  
**Status:** `todo`  
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

- [ ] A baseline flow can be executed and logged for comparison against the semantic interface.
- [ ] Session exports contain the fields needed for planned interaction metrics.
- [ ] A small set of pilot scenarios or tasks is documented and runnable.
- [ ] Missing telemetry fields, if any, are identified explicitly rather than ignored.
- [ ] The resulting note is actionable for later study preparation.

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
- [ ] evaluation smoke checks
- [ ] docs review
- [ ] manual baseline run-through

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

- [ ] Goal is implemented.
- [ ] All acceptance criteria are satisfied.
- [ ] Required tests and checks pass.
- [ ] No blocking review issues remain.
- [ ] Docs/comments are updated if behavior changed.
- [ ] Changes are committed with the ticket ID.
- [ ] Ticket status is updated to `done`.

---

## 10. Deliverables

- baseline evaluation notes
- telemetry validation note
- pilot scenario pack or checklist

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
