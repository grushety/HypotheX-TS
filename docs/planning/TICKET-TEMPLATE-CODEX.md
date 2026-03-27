# TICKET-TEMPLATE-CODEX.md

## Ticket Header

**Ticket ID:** `HTS-XXX`  
**Title:** `<short action-oriented title>`  
**Status:** `todo | in_progress | blocked | review | done`  
**Priority:** `P0 | P1 | P2 | P3`  
**Type:** `feature | bug | refactor | test | docs | research-spike`  
**Depends on:** `<ticket IDs or none>`  
**Blocked by:** `<ticket IDs or none>`  
**Owner:** `Codex`  
**Branch:** `<branch-name>`

---

## 1. Goal

Describe the user-visible or system-visible outcome in 2–5 sentences.

Include:
- what should change,
- why the change is needed,
- which part of HypotheX-TS it affects.

Example:
> Add manual segment boundary editing in the timeline view so users can drag boundaries between adjacent segments and update the segmentation overlay without reloading the page.

---

## 2. Scope

### In scope
- `<explicit item>`
- `<explicit item>`
- `<explicit item>`

### Out of scope
- `<explicit exclusion>`
- `<explicit exclusion>`
- `<explicit exclusion>`

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

List the files or docs Codex must read before editing code.

Required minimum:
- `Rules.txt`
- `CODEX_RULES.md`
- this ticket

Add task-specific context, for example:
- `MyPaper-HypotheX-TS - Methodology.md`
- `HypotheX-TS - Technical Plan.md`
- `HypotheX-TS - Formal Definitions.md`
- relevant API contracts
- relevant frontend/backend module docs

---

## 4. Affected Areas

### Likely files or modules
- `<path or module>`
- `<path or module>`
- `<path or module>`

### Architecture layer
Mark all that apply:
- [ ] frontend
- [ ] backend
- [ ] API contract
- [ ] domain logic
- [ ] model/data
- [ ] tests
- [ ] docs

### Risk level
`low | medium | high`

Brief reason:
> `<one or two sentences>`

---

## 5. Inputs and Expected Outputs

### Inputs
- `<user action, API payload, function input, or dataset assumption>`
- `<input>`

### Expected outputs
- `<UI change, API response, state transition, file output, or log event>`
- `<output>`

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

Use clear, testable statements.

- [ ] `<criterion 1>`
- [ ] `<criterion 2>`
- [ ] `<criterion 3>`
- [ ] `<error or edge case criterion>`
- [ ] `<constraint or logging criterion, if relevant>`

Acceptance criteria must describe observable outcomes, not implementation preferences.

Example:
- [ ] Dragging a segment boundary updates the two adjacent segments only.
- [ ] Segment labels remain unchanged after boundary movement unless explicitly edited.
- [ ] Invalid boundary moves produce a visible warning and do not corrupt state.
- [ ] Boundary edits are recorded in the audit log.

---

## 7. Implementation Notes

Provide constraints Codex must respect.

Examples:
- keep route handlers thin,
- do not place domain logic in UI components,
- preserve existing API response shape,
- prefer service-layer changes over component-layer hacks,
- use existing segment model and audit-log utilities.

Also list any known pitfalls.

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [ ] relevant unit tests
- [ ] relevant integration or smoke tests
- [ ] lint or static checks
- [ ] API contract validation if applicable
- [ ] manual verification steps if UI behavior changes

### Commands
```bash
# Replace with project-specific commands
<test command>
<lint command>
<integration command>
```

### Manual verification
1. `<step>`
2. `<step>`
3. `<step>`

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

List exactly what Codex should leave behind.

Examples:
- updated component and service files,
- new unit tests,
- API contract update,
- audit-log support,
- docs note.

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
`hts/<ticket-id>-<short-slug>`

Example:
`hts/hts-012-boundary-editing`

### Commit message
`<TICKET-ID>: <short description>`

Example:
`HTS-012: add manual segment boundary editing`

---

## 13. Status Update Block

Use this block while the ticket is active.

**Current status:** `<todo | in_progress | blocked | review | done>`  
**What changed:** `<1–5 bullet summary>`  
**Checks run:** `<tests/checks executed>`  
**Blockers:** `<none or brief note>`  
**Next step:** `<single next action>`

---

## 14. Completion Note

Fill this only when the ticket is done.

**Completed on:** `<date>`  
**Summary:** `<brief summary of implemented result>`  
**Tests passed:** `<list>`  
**Files changed:** `<list or summary>`  
**Follow-up tickets needed:** `<IDs or none>`

---

## 15. Minimal Example

### Example ticket

**Ticket ID:** `HTS-012`  
**Title:** `Add manual segment boundary editing`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-005`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-012-boundary-editing`

### Goal
Add manual segment boundary editing to the timeline so a user can drag a shared boundary between adjacent segments. The change should update the overlay immediately and preserve the current label assignments unless the user explicitly edits them.

### In scope
- dragging an existing boundary,
- updating adjacent segment ranges,
- state validation,
- audit-log entry.

### Out of scope
- creating new segments from scratch,
- multi-boundary batch editing,
- model retraining.

### Acceptance Criteria
- [ ] Dragging a shared boundary updates only the two adjacent segments.
- [ ] Invalid moves are rejected with a visible warning.
- [ ] Segment labels remain unchanged after a valid move.
- [ ] The action is recorded in the audit log.
- [ ] Unit tests cover valid and invalid edits.

### Verification Plan
- [ ] run relevant frontend tests
- [ ] run domain-logic tests for segment updates
- [ ] manually verify drag behavior in the timeline view

### Definition of Done
- [ ] all acceptance criteria pass
- [ ] tests pass
- [ ] ticket status updated to `done`
- [ ] commit created with `HTS-012` in message

---

## 16. Template Usage Rules

- Keep one ticket focused on one deliverable.
- Prefer smaller tickets over broad implementation bundles.
- Every ticket must include at least one verifiable edge case.
- Every UI ticket should include manual verification steps.
- Every API or domain ticket should include contract verification.
- If the ticket becomes too large, split it before implementation.
- Do not mark a ticket done while verification is incomplete.
- Use follow-up tickets instead of adding adjacent features opportunistically.
