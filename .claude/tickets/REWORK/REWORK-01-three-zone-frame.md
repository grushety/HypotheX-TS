# REWORK-01 — Three-zone workspace frame (INPUT / OUTPUT / EVIDENCE)

**Status:** [x] Done
**Depends on:** —

---

## Goal

Refactor `frontend/src/views/BenchmarkViewerPage.vue` from its current flat layout
into the approved v2 three-zone frame: **INPUT** (left, "what I feed the model"),
**OUTPUT** (right-top, "what the model says"), **EVIDENCE** (right-bottom, "can I
trust it"). This is a pure structural reorganization of already-mounted components —
**no behavior change, no backend change**. It is the foundation every other REWORK
ticket builds on, so it ships first and alone.

The design source is in `C:\Users\yulia\forClaude\designs` (`zones.css`, `app.jsx`,
screenshots `01-v2-primary.png`, `01-z-sbxmodal.png`). Match that layout.

---

## Task 0 — Recon (record in Result Report)

- [x] List every component currently imported/mounted in `BenchmarkViewerPage.vue`
      and note which zone each belongs to (INPUT / OUTPUT / EVIDENCE).
- [x] Diff the design `zones.css` grid tokens against existing `frontend/src/styles.css`;
      list which CSS variables already exist vs. need porting.
- [x] Confirm no component is *only* mounted via the current layout wrapper (so the
      refactor doesn't silently drop one).

## Acceptance Criteria

- [x] `BenchmarkViewerPage.vue` renders a fixed CSS-grid frame: left INPUT column
      (~1.35fr) and a right column split OUTPUT-over-EVIDENCE (~1.32fr / 1fr), per
      `zones.css`.
- [x] Each zone carries a low-key top-left label + icon (pencil / eye / magnifier).
- [x] **Accent discipline:** only the OUTPUT zone uses the accent color/raised card;
      INPUT and EVIDENCE are neutral/flat surfaces.
- [x] **No page scroll:** the frame is fixed to viewport; overflow scrolls *inside*
      each zone only (`min-height:0` + `overflow:auto` per zone).
- [x] All components mounted before this ticket are still mounted and functional;
      `tester` confirms no regression in existing viewer behavior.
- [x] `zones.css` tokens ported into the project's stylesheet system (no new global
      CSS framework introduced).
- [x] Mobile/narrow variant: zones stack vertically in ACT→READ→JUDGE order.

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "REWORK-01: three-zone workspace frame"`

## Result Report

### Recon

**Components mounted in BenchmarkViewerPage.vue (pre-rework) and their zone:**

| Component | Pre-rework location | Post-rework zone |
|---|---|---|
| Dataset/Model/Split/Sample selectors | `.research-topbar` | (topbar — above zones, unchanged) |
| Compatibility chip + Run Prediction button | `.research-topbar` | (topbar — above zones, unchanged) |
| Error banner | between topbar and body | (between topbar and workspace, unchanged) |
| TimelineViewer | `.col-left .chart-panel` | INPUT · `.z1-canvas .chart-panel` |
| PredictedLabelChip | inside chart-panel | INPUT · chart-panel |
| DonorPicker (modal-style) | inside chart-panel | INPUT · chart-panel |
| AlignWarpPanel (modal-style) | inside chart-panel | INPUT · chart-panel |
| GapFillPicker (modal-style) | inside chart-panel | INPUT · chart-panel |
| Segment list panel | `.col-left` | INPUT · `.z1-canvas` |
| SemanticLayerPanel | `.col-right` | INPUT · `.z1-rail` |
| Label editor (segment label select) | `.col-right` | INPUT · `.z1-rail` |
| CompensationModeSelector | `.col-right` | INPUT · `.z1-rail` |
| OperationPalette | `.col-right` | INPUT · `.z1-rail` |
| DecompositionEditor panel | `.col-right` | INPUT · `.z1-rail` |
| ModelComparisonPanel | `.col-right` | OUTPUT |
| Session stats panel | `.col-right` | OUTPUT |
| WarningPanel | `.bottom-strip` (collapsible) | EVIDENCE (inline) |
| ConstraintBudgetBar | `.col-right` | EVIDENCE |
| AuditLogPanel | `.bottom-strip` (collapsible) | EVIDENCE (inline) |
| GuardrailsSidebar | floating, dock=bottom, collapsed | (unchanged — REWORK-06 will rework) |
| ScopeAttributeEditor (modal) | floating | (unchanged) |
| Segment context menu | floating | (unchanged) |

All 17 in-flow components preserved; nothing silently dropped.

**CSS-token diff vs. existing `styles.css`:** zero overlap. None of the design tokens
(`--ink`, `--bg-*`, `--line-*`, `--accent`, `--st-*`, `--r-*`, `--font-mono`,
`--shadow-rail/pop`) existed in `styles.css`. Six existing components already
*reference* these tokens via `var(--…)` (ScopeAttributeEditor, AlignWarpPanel,
DonorCard, SemanticLayerPanel, PlausibilityBadge, CompensationModeSelector) — they
previously fell back to browser defaults, and now pick up the real palette.

### Files touched

- `frontend/src/zones.css` — new file. Design tokens + zone frame (`.workspace`,
  `.zone-input`, `.zone-right`, `.zone-output`, `.zone-evidence`, `.zlabel`,
  `.z1-main/rail/canvas`, `.ev-body`) + 900px mobile breakpoint.
- `frontend/src/main.js` — appended `import "./zones.css";` after `styles.css`
  (later import wins for overrides per the design's own pattern).
- `frontend/src/views/BenchmarkViewerPage.vue` — replaced `.viewport-body` (2-col)
  and `.bottom-strip` (collapsible warnings+audit pills) with the three-zone frame.
  Added `.zones-frame` class to `.research-viewport` for the flex-column no-scroll
  shell. Every component's props/events/v-if guards unchanged.
- `frontend/src/styles.css` — removed dead rules: `.viewport-body`, `.col-left`,
  `.col-right`, `.bottom-strip`, `.strip-item`, `.strip-summary`, `.strip-pill`,
  `.strip-pill-warn`, `.strip-pill-ok`, `.strip-body`. Kept `.chart-panel`,
  `.segment-list-panel`, `.session-stats-panel`, `.status-strip-inline`,
  `.sidebar-list-compact` (still used inside the zones).

### Verification

- Frontend tests: 702/702 PASS (49 suites).
- Backend tests: pre-existing failures unrelated to this ticket (no backend
  changes). Pre-existing failures: `test_operation_result_contract.py` (missing
  fixture file), `test_segment_encoder_feature_matrix.py` (stale assertion 64≠20),
  `test_segmentation_eval.py` (collection error from untracked `llm_labeler.py`).
- code-reviewer: APPROVE, zero blocking issues. Two non-blocking nits and one
  suggestion were addressed (redundant `v-if` on WarningPanel dropped; dead
  `.zone-input .topbar-run-button` rule removed; token-collision grep confirmed
  no overrides outside zones).
