# HTS-003 — Render segmentation overlay and labels

**Ticket ID:** `HTS-003`  
**Title:** `Render segmentation overlay and labels`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `HTS-002`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-003-render-segmentation-overlay-and-labels`

---

## 1. Goal

Render segment boundaries, segment spans, and labels on top of the viewer chart. The overlay should visually distinguish segments and prepare the UI for later selection and editing.

---

## 2. Scope

### In scope
- overlay layer bound to current segment list
- visible segment boundaries
- visible labels for each segment
- basic overlay legend or styling hooks if needed

### Out of scope
- editing boundaries
- changing labels
- operations palette
- constraints feedback

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
- `src/components/viewer/SegmentationOverlay.*`
- `src/components/viewer/TimeSeriesChart.*`
- `src/lib/segments/`

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
> This is the first semantic layer and directly enables later segment-centered interactions.

---

## 5. Inputs and Expected Outputs

### Inputs
- series values
- initial segment list
- segment labels

### Expected outputs
- visible overlay
- segment spans and boundaries
- label rendering

---

## 6. Acceptance Criteria

- [ ] segment boundaries are visible on the chart
- [ ] segment labels are visible and aligned with the current segment spans
- [ ] overlay rendering stays synchronized with the loaded sample and segment list
- [ ] overlay does not corrupt or hide the underlying chart

---

## 7. Implementation Notes

- treat the segment as the core UI unit
- keep overlay rendering separate from raw chart drawing

---

## 8. Verification Plan

### Required checks
- [ ] relevant frontend unit tests
- [ ] manual overlay verification

### Commands
```bash
# fill with repo-specific commands
```

### Manual verification
1. Open a sample with segments
2. Check every segment boundary appears once
3. Check labels remain readable and aligned

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

- overlay component
- overlay integration
- overlay tests

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
`hts/hts-003-render-segmentation-overlay-and-labels`

### Commit message
`HTS-003: render segmentation overlay and labels`
