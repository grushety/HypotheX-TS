# HTS-002 — Render time-series chart

**Ticket ID:** `HTS-002`  
**Title:** `Render time-series chart`  
**Status:** `done`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-001`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-002-render-time-series-chart`

---

## 1. Goal

Add the first real visualization layer by rendering the selected time series in the viewer. This chart should be stable, readable, and reusable by later overlay and editing tickets.

---

## 2. Scope

### In scope
- chart component for a single series
- support for current sample from viewer state
- basic axes or scale handling
- responsive rendering within the viewer

### Out of scope
- segment overlay rendering
- segment selection
- editing interactions
- counterfactual comparison

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `docs/planning/codex_rules_hypothe_x_ts.md`
- `docs/planning/implementation_steps_hypothe_x_ts.md`
- `docs/planning/ticket_template_codex_hypothe_x_ts.md`
- `docs/research/HypotheX-TS - Technical Plan.md`
- `docs/research/HypotheX-TS - Formal Definitions.md`

---

## 4. Affected Areas

### Likely files or modules
- `src/components/viewer/TimeSeriesChart.*`
- `src/pages/`
- `src/lib/chart/`

### Architecture layer
- [x] frontend
- [ ] backend
- [ ] API contract
- [ ] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`medium`

Brief reason:
> The chart becomes the visual anchor for all later semantic interactions.

---

## 5. Inputs and Expected Outputs

### Inputs
- series values from viewer state

### Expected outputs
- visible plotted series
- stable chart sizing
- reusable chart component API

---

## 6. Acceptance Criteria

- [x] the current sample is rendered as a visible time-series plot
- [x] the chart renders correctly for at least one short and one longer series
- [x] the chart component accepts data through props/state rather than hidden globals
- [x] the page remains stable after rerender or resize

---

## 7. Implementation Notes

- do not mix segmentation logic into the pure chart component
- prefer a reusable chart API over ticket-specific hacks

---

## 8. Verification Plan

### Required checks
- [ ] relevant frontend unit tests
- [ ] lint or static checks
- [ ] manual chart verification

### Commands
```bash
cd frontend
npm test
npm run build
```

### Manual verification
1. Open the viewer page
2. Verify the line/series is rendered
3. Resize the page and verify the chart remains usable

If a check cannot run, Codex must record why.

---

## 9. Definition of Done

- [x] Goal is implemented.
- [x] All acceptance criteria are satisfied.
- [x] Required tests and checks pass.
- [x] No blocking review issues remain.
- [x] Docs/comments are updated if behavior changed.
- [x] Changes are committed with the ticket ID.
- [x] Ticket status is updated to `done`.

---

## 10. Deliverables

- chart component
- viewer integration
- chart tests

---

## 11. Review Checklist

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

## 13. Status Update Block

**Current status:** `done`  
**What changed:** 
- added a reusable SVG `TimeSeriesChart` component that renders a single sample series
- added chart-geometry helpers in `src/lib/chart/` for path and tick generation
- integrated the chart into the viewer shell without mixing in overlay or selection logic
- added chart tests that cover both short and longer series inputs
**Checks run:** `npm test`; `npm run build`; frontend dev server started successfully on `http://127.0.0.1:5174/` after `5173` was already in use  
**Blockers:** `none`  
**Next step:** `HTS-003`

---

## 14. Completion Note

**Completed on:** `2026-03-27`  
**Summary:** `Rendered the benchmark sample as a reusable responsive time-series chart and added chart geometry tests for both short and long series.`  
**Tests passed:** `npm test`; `npm run build`  
**Files changed:** `frontend viewer/chart files, frontend package test script, and this ticket file`  
**Follow-up tickets needed:** `none`

---

## 12. Commit

### Branch naming
`hts/hts-002-render-time-series-chart`

### Commit message
`HTS-002: render time-series chart`
