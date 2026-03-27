# HTS-001 — Scaffold benchmark viewer page

**Ticket ID:** `HTS-001`  
**Title:** `Scaffold benchmark viewer page`  
**Status:** `todo`  
**Priority:** `P1`  
**Type:** `feature`  
**Depends on:** `none`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-001-scaffold-benchmark-viewer-page`

---

## 1. Goal

Create the first app page that loads a benchmark dataset sample and renders the base viewer shell for HypotheX-TS. This ticket should establish the page layout, data-loading boundary, and placeholder regions for the chart, overlay, and side panel.

---

## 2. Scope

### In scope
- viewer route or page scaffold
- benchmark sample loading hook or adapter
- empty chart container
- empty side panel and status area

### Out of scope
- segmentation overlay rendering
- boundary editing
- semantic operations
- constraints logic

Codex must not implement out-of-scope work under this ticket.

---

## 3. Context to Read First

- `Rules.txt`
- `docs/planning/codex_rules_hypothe_x_ts.md`
- `docs/planning/implementation_steps_hypothe_x_ts.md`
- `docs/planning/ticket_template_codex_hypothe_x_ts.md`
- `docs/research/HypotheX-TS - Technical Plan.md`
- `docs/research/HypotheX-TS - Formal Definitions.md`
- `docs/planning/implementation_steps_hypothe_x_ts.md`

---

## 4. Affected Areas

### Likely files or modules
- `app/`
- `src/pages/`
- `src/components/viewer/`
- `src/lib/data/`

### Architecture layer
- [x] frontend
- [ ] backend
- [ ] API contract
- [ ] domain logic
- [ ] model/data
- [x] tests
- [x] docs

### Risk level
`low`

Brief reason:
> Creates the visible entry point for all later MVP work without committing to deeper interaction logic yet.

---

## 5. Inputs and Expected Outputs

### Inputs
- benchmark dataset identifier
- single series sample
- basic page state

### Expected outputs
- rendered viewer page
- loaded sample in component state
- placeholder regions for future modules

---

## 6. Acceptance Criteria

- [ ] viewer page opens without runtime errors
- [ ] a benchmark sample loads into the page state
- [ ] chart area, overlay area, and side panel placeholders are visible
- [ ] component structure is ready for follow-up tickets

---

## 7. Implementation Notes

- keep the page shell simple and stable
- do not hardcode future operation behavior
- separate loading logic from presentational components

---

## 8. Verification Plan

### Required checks
- [ ] relevant frontend unit tests
- [ ] lint or static checks
- [ ] manual page verification

### Commands
```bash
# fill with repo-specific commands
```

### Manual verification
1. Open the viewer page
2. Confirm a sample series loads
3. Confirm shell regions are visible and stable

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

- viewer page/component scaffold
- data-loading adapter or hook
- basic page tests
- small docs note if routing/setup changed

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
`hts/hts-001-scaffold-benchmark-viewer-page`

### Commit message
`HTS-001: scaffold benchmark viewer page`
