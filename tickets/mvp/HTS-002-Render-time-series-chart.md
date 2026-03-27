# HTS-002 — Render time-series chart

**Ticket ID:** `HTS-002`  
**Title:** `Render time-series chart`  
**Status:** `todo`  
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

- [ ] the current sample is rendered as a visible time-series plot
- [ ] the chart renders correctly for at least one short and one longer series
- [ ] the chart component accepts data through props/state rather than hidden globals
- [ ] the page remains stable after rerender or resize

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
# fill with repo-specific commands
```

### Manual verification
1. Open the viewer page
2. Verify the line/series is rendered
3. Resize the page and verify the chart remains usable

If a check cannot run, Codex must record why.

---

## 9. Definition of Done

- [ ] Goal is implemented.
- [ ] All acceptance criteria are satisfied.
- [ ] Required tests and checks pass.
- [ ] No blocking review issues remain.
- [ ] Docs/comments are updated if behavior changed.
- [ ] Changes are committed with the ticket ID.
- [ ] Ticket status is updated to `done`.

---

## 10. Deliverables

- chart component
- viewer integration
- chart tests

---

## 11. Review Checklist

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
`hts/hts-002-render-time-series-chart`

### Commit message
`HTS-002: render time-series chart`
