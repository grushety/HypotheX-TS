## Ticket Header

**Ticket ID:** `HTS-402`  
**Title:** `Add manual segmentation editing in the timeline`  
**Status:** `done`  
**Priority:** `P0`  
**Type:** `feature`  
**Depends on:** `HTS-302, HTS-401`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-402-manual-editing-ui`

---

## 1. Goal

Add manual semantic segmentation editing to the timeline so users can drag boundaries and invoke split, merge, and relabel actions. This is the minimum interaction loop needed before model suggestions matter.

---

## 2. Scope

### In scope
- dragging shared boundaries
- split action in UI
- merge adjacent action in UI
- relabel action in UI

### Out of scope
- typed value operations
- model suggestion UI
- advanced multi-select editing

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `TICKET-TEMPLATE-CODEX.md`
- `HypotheX-TS - Technical Plan.md`
- `MyPaper-HypotheX-TS - Semantic Chunk Types and Typed Operation - Revised.md`

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
- [ ] docs

### Risk level
`high`

Brief reason:
> This is the first high-friction interaction path. UI and backend semantics can easily diverge if boundary handling is not precise.

---

## 5. Inputs and Expected Outputs

### Inputs
- mouse/touch boundary drag
- split/merge/relabel user action
- current segmentation state

### Expected outputs
- updated overlay
- visible validation feedback
- state synced with backend

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [x] Dragging a boundary updates only the two adjacent segments.
- [x] Split, merge, and relabel actions update the overlay without reloading the page.
- [x] Invalid edits show visible feedback and do not corrupt UI state.
- [x] Segment labels remain unchanged after boundary edits unless explicitly relabeled.
- [x] Manual edits are compatible with backend audit logging.

---

## 7. Implementation Notes

- Do not implement business rules in the component; call the backend/service contract.
- Keep drag behavior predictable and debuggable.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [x] frontend interaction tests
- [x] lint
- [x] manual UI verification

### Commands
```bash
npm test -- --runInBand
npm run lint
npm run build
```

### Manual verification
1. Drag a shared boundary.
2. Attempt an invalid drag.
3. Split and merge a segment.
4. Relabel one segment and inspect the overlay update.

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

- manual editing UI
- frontend tests
- state wiring updates

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

**Current status:** `done`  
**What changed:** `Added derived manual-editing state for split, merge, and relabel actions; reset stale selection-driven form state; and extended audit-focused tests so manual edits remain compatible with interaction logging.`  
**Checks run:** `npm test -- --runInBand; npm run lint; npm run build; frontend dev-server smoke check`  
**Blockers:** `none`  
**Next step:** `HTS-403`

---

## 14. Completion Note

**Completed on:** `2026-03-29`  
**Summary:** `Stabilized the manual timeline editing loop by deriving split and merge affordances from the selected segment, clearing stale edit state on selection changes, and verifying that manual edits still produce audit-ready events.`  
**Tests passed:** `npm test -- --runInBand; npm run lint; npm run build`  
**Files changed:** `frontend/src/components/operations/OperationPalette.vue; frontend/src/lib/viewer/createManualEditingState.js; frontend/src/lib/viewer/createManualEditingState.test.js; frontend/src/lib/audit/auditEvents.test.js; frontend/src/views/BenchmarkViewerPage.vue; frontend/src/styles.css`  
**Follow-up tickets needed:** `none`
