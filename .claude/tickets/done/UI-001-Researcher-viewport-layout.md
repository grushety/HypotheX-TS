# UI-001 — Refactor to researcher viewport layout

**Status:** [x] Done
**Depends on:** HTS-404

---

## Goal

Restructure the frontend so everything fits in one viewport with no page-level scroll. Currently five panels stack vertically — the run button, warnings, and audit log are all below the fold. Researchers need to see data, controls, and the action button simultaneously.

New layout:
- **Topbar:** dataset / model / split / sample selectors + compatibility indicator + ▶ Run Prediction button — one row, always visible
- **Left column (≈65%):** time-series chart + segmentation track + segment list (list scrolls internally)
- **Right column (≈35%):** label editor + operation palette → model comparison (suggest / accept / override) → session stats — stacked, always visible
- **Bottom strip:** warnings pill (collapsed by default, expands on click) + audit log + export button

No logic changes. All existing event bindings and props stay wired. Only layout and presentation change.

---

## Acceptance Criteria

- [ ] No vertical scrollbar on `<body>` at 1280×800
- [ ] Hero section removed
- [ ] All four selectors + Run Prediction button are in the topbar and functional
- [ ] Chart fills left column; segment list scrolls within its own box
- [ ] Label editor, operations, model comparison, session stats are in the right column and functional
- [ ] Warning strip is collapsed by default; expands on click showing warning detail
- [ ] History strip shows event count collapsed; expands with audit log and export button
- [ ] Boundary drag, label edit, run operation, accept/override suggestion, export log all still work
- [ ] No console errors or Vue warnings

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass (`cd frontend && npm test && npm run build`)
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "UI-001: refactor to researcher viewport layout"`
- [ ] Update Status to `[x] Done`

## Work Done
- `frontend/src/views/BenchmarkViewerPage.vue` — replaced hero + stacked panels template with topbar/viewport-body/bottom-strip structure; swapped BenchmarkSelectorPanel/PredictionPanel/ViewerShell imports for direct sub-component imports; added inline topbar selectors and collapsible bottom-strip using `<details>`
- `frontend/src/styles.css` — changed `html/body/#app` to `height:100vh; overflow:hidden`; added all new viewport layout classes (`.research-viewport`, `.research-topbar`, `.viewport-body`, `.col-left`, `.col-right`, `.segment-list-panel`, `.bottom-strip`, `.strip-*`)
