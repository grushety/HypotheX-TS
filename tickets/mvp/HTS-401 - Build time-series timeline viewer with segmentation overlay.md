## Ticket Header

**Ticket ID:** `HTS-401`  
**Title:** `Build time-series timeline viewer with segmentation overlay`  
**Status:** `done`  
**Priority:** `P0`  
**Type:** `feature`  
**Depends on:** `HTS-201`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-401-timeline-viewer`

---

## 1. Goal

Build the core timeline UI that visualizes the time series together with its segmentation overlay. This is the visual foundation for semantic editing and must clearly display segment boundaries, labels, and selected state before any advanced interaction is added.

---

## 2. Scope

### In scope
- time-series chart
- segmentation overlay band
- selected segment highlighting
- basic zoom/pan or minimap support if already feasible

### Out of scope
- drag editing behavior
- operation palette
- model comparison panel

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `CODEX_RULES.md`
- this ticket
- `HypotheX-TS - Technical Plan.md`
- `MyPaper-HypotheX-TS - Semantic Chunk Types and Typed Operation - Revised.md`
- `MyPaper-HypotheX-TS - ML Model Approach - Revised.md`

---

## 4. Affected Areas

### Likely files or modules
- `frontend/src/components/`
- `frontend/src/pages/`
- `frontend/src/types/`
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
> The timeline becomes the central interaction surface. If it is visually unclear, all later operations will feel brittle.

---

## 5. Inputs and Expected Outputs

### Inputs
- time series payload
- segmentation payload
- selection state

### Expected outputs
- rendered chart with visible segment overlay and selected segment state

This section should be concrete enough that Codex can verify behavior.

---

## 6. Acceptance Criteria

- [x] The main time series and segmentation overlay render together.
- [x] Segment boundaries are visually distinguishable.
- [x] Selected segment state is visible and updates correctly.
- [x] The component tolerates longer series without breaking layout.
- [x] Basic rendering tests or smoke tests cover the component.

---

## 7. Implementation Notes

- Keep business logic out of the component.
- Use typed props aligned with the shared schemas.
- Do not implement mutation behavior under this ticket.

Known pitfalls:
- avoid mixing domain logic into UI components or route handlers
- preserve shared schema names and field meanings
- add follow-up tickets instead of adjacent scope creep

---

## 8. Verification Plan

Codex must run the checks listed here before completion.

### Required checks
- [x] frontend tests
- [x] lint
- [x] build or type-check

### Commands
```bash
npm test -- --runInBand
npm run lint
npm run build
```

### Manual verification
1. Open a sample series.
2. Verify segment overlay alignment.
3. Select multiple segments and confirm highlight behavior.

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

- timeline viewer component(s)
- basic tests
- type definitions if needed

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
**What changed:** `Added a dedicated timeline viewer component, a pure viewer model for selection and overview state, a minimap for longer series, and focused frontend coverage for the new timeline contract.`  
**Checks run:** `npm test -- --runInBand; npm run lint; npm run build`  
**Blockers:** `none`  
**Next step:** `HTS-402`

---

## 14. Completion Note

**Completed on:** `2026-03-29`  
**Summary:** `Built a timeline-centered viewer surface that renders the chart and segmentation overlay together, adds an overview minimap for longer series, and keeps selected segment state visible across the timeline and segment index.`  
**Tests passed:** `npm test -- --runInBand; npm run lint; npm run build`  
**Files changed:** `frontend/src/components/viewer/TimelineViewer.vue; frontend/src/components/viewer/ViewerShell.vue; frontend/src/lib/viewer/createTimelineViewerModel.js; frontend/src/lib/viewer/createTimelineViewerModel.test.js; frontend/src/lib/segments/createSegmentationOverlayModel.js; frontend/src/views/BenchmarkViewerPage.vue; frontend/src/styles.css; frontend/package.json; frontend/scripts/lint.mjs`  
**Follow-up tickets needed:** `none`
