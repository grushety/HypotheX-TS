## Ticket Header

**Ticket ID:** `HTS-403`  
**Title:** `Build operation palette and model comparison panel`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-304, HTS-401`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-403-operation-palette`

---

## 1. Goal

Build the UI layer that shows typed operations for the selected chunk and compares model-proposed segmentation with the current user segmentation. This ticket makes the semantic interaction concept visible and actionable in the interface.

---

## 2. Scope

### In scope
- operation palette filtered by legal operations
- PASS/WARN/FAIL feedback rendering
- model-vs-user comparison panel with disagreement highlights

### Out of scope
- training-time model adaptation
- advanced explanation analytics
- session export UI

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `MyPaper-HypotheX-TS - ML Model Approach - Revised.md`
- `MyPaper-HypotheX-TS - Semantic Chunk Types and Typed Operation - Revised.md`
- `HypotheX-TS - Technical Plan.md`
- `HypotheX-TS - Novelty Positioning.md`

---

## 4. Affected Areas

### Likely files or modules
- `frontend/src/components/`
- `frontend/src/state/`
- `frontend/src/tests/`

### Architecture layer
Mark all that apply:
- [x] frontend
- [ ] backend
- [x] API contract
- [ ] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`medium`

Brief reason:
> If validity feedback and model disagreement are unclear, the interface will not communicate the project’s central contribution.

---

## 5. Inputs and Expected Outputs

### Inputs
- selected segment
- legal operations list
- operation result contract
- model proposal payload

### Expected outputs
- filtered operation palette
- visible constraint feedback
- disagreement visualizations for user vs model

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [ ] The selected segment shows only the operations that are legal for its chunk type.
- [ ] PASS/WARN/FAIL feedback is visible after an attempted operation.
- [ ] Model-proposed segmentation can be viewed alongside the user segmentation.
- [ ] Boundary or label disagreement is visually highlighted.
- [ ] Frontend logic does not reimplement legality or constraint rules locally.

---

## 7. Implementation Notes

- Keep UI text clear and concise.
- Use backend-provided legality and feedback rather than duplicating domain logic in the client.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [ ] frontend component tests
- [ ] lint
- [ ] manual UI verification

### Commands
```bash
npm test -- --runInBand
npm run lint
npm run build
```

### Manual verification
1. Select different chunk types and inspect the operation palette.
2. Trigger PASS/WARN/FAIL feedback.
3. Compare a model proposal against a user-edited segmentation.

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

- operation palette UI
- comparison panel UI
- tests

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
