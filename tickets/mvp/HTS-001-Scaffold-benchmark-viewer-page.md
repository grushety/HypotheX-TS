# HTS-001 — Scaffold benchmark viewer page

**Ticket ID:** `HTS-001`  
**Title:** `Scaffold benchmark viewer page`  
**Status:** `done`  
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

- [x] viewer page opens without runtime errors
- [x] a benchmark sample loads into the page state
- [x] chart area, overlay area, and side panel placeholders are visible
- [x] component structure is ready for follow-up tickets

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
cd frontend
npm test
npm run build
```

### Manual verification
1. Open the viewer page
2. Confirm a sample series loads
3. Confirm shell regions are visible and stable

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

- viewer page/component scaffold
- data-loading adapter or hook
- basic page tests
- small docs note if routing/setup changed

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
- replaced the HTS-000 connectivity screen with a benchmark viewer page scaffold
- added a benchmark sample loader adapter backed by an ECG200 sample
- added viewer shell components for chart, overlay, and side panel placeholders
- added frontend unit tests for the loader and viewer page state mapping
**Checks run:** `npm test`; `npm run build`; frontend dev server started successfully on `http://127.0.0.1:5173/`  
**Blockers:** `none`  
**Next step:** `HTS-002`

---

## 14. Completion Note

**Completed on:** `2026-03-27`  
**Summary:** `Implemented the initial benchmark viewer shell, loaded an ECG200 sample into page state, and added frontend verification for the loader and scaffold state.`  
**Tests passed:** `npm test`; `npm run build`  
**Files changed:** `frontend app shell, viewer components, benchmark sample adapter, frontend tests, and this ticket file`  
**Follow-up tickets needed:** `none`

---

## 12. Commit

### Branch naming
`hts/hts-001-scaffold-benchmark-viewer-page`

### Commit message
`HTS-001: scaffold benchmark viewer page`
