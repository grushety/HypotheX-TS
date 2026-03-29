## Ticket Header

**Ticket ID:** `HTS-404`  
**Title:** `Add session log panel and export controls`  
**Status:** `todo`  
**Priority:** `P2`  
**Type:** `feature`  
**Depends on:** `HTS-305, HTS-401`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-404-session-panel`

---

## 1. Goal

Add a simple session panel that lets users inspect the chronological action history and export their session. This supports debugging now and later user-study telemetry review.

---

## 2. Scope

### In scope
- session log panel
- ordered action list rendering
- session export control

### Out of scope
- full analytics dashboard
- study-specific scoring views
- complex search/filtering over logs

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `HypotheX-TS - Evaluation.md`
- `HypotheX-TS - Research Plan.md`
- `HypotheX-TS - Technical Plan.md`

---

## 4. Affected Areas

### Likely files or modules
- `frontend/src/components/`
- `frontend/src/tests/`

### Architecture layer
Mark all that apply:
- [x] frontend
- [ ] backend
- [x] API contract
- [ ] domain logic
- [ ] model/data
- [x] tests
- [ ] docs

### Risk level
`low`

Brief reason:
> This is a thin UI layer over an existing backend export path, but it becomes important for observability.

---

## 5. Inputs and Expected Outputs

### Inputs
- session log payload
- export endpoint or utility

### Expected outputs
- readable log panel
- downloadable export action

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [ ] The UI shows an ordered list of recorded actions.
- [ ] Each log entry displays action type and status in a readable way.
- [ ] The user can export the session without developer tools.
- [ ] Rendering tolerates empty and non-empty sessions.
- [ ] Basic smoke tests cover the panel.

---

## 7. Implementation Notes

- Do not turn this into a dashboard under this ticket.
- Favor readability over dense detail.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [ ] frontend tests
- [ ] lint
- [ ] manual verification

### Commands
```bash
npm test -- --runInBand
npm run lint
npm run build
```

### Manual verification
1. Perform a few edits.
2. Open the session panel.
3. Export the session and inspect the downloaded content.

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

- session panel UI
- export control wiring
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
