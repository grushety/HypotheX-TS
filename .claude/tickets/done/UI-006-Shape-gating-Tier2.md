# UI-006 — Shape-gating logic for Tier-2 buttons

**Status:** [x] Done
**Depends on:** UI-005

---

## Goal

Implement the gating logic that enables/disables Tier-2 buttons based on the active segment's shape. The gating table is authored from [[_project HypotheX-TS/HypotheX-TS - Operation Vocabulary Research]] §7 — not invented in UI.

**Why:** Without shape-gating, users would see all 39 Tier-2 ops at once and be confused about which apply to their segment. With gating, the palette teaches the shape → op mapping implicitly.

---

## Acceptance Criteria

- [x] `frontend/src/lib/viewer/shapeGating.js` with `SHAPE_GATING_TABLE: Record<ShapeLabel, string[]>` mapping each shape to the list of legal Tier-2 ops
- [x] Table copied verbatim from [[_project HypotheX-TS/HypotheX-TS - Operation Vocabulary Research]] §7 — snapshot test asserts bit-identical content
- [x] `useShapeGating(activeSelection)` composable returns `{ isEnabled(op_name), tooltipIfDisabled(op_name) }`
- [x] Multi-select uses **intersection** of legal ops across selected shapes; empty intersection disables all Tier-2 buttons
- [x] Disabled buttons show informative tooltip: `"Not available for {shape}; applies to {eligible_shapes}"`
- [x] Gating updates reactively on selection change (Vue `computed`)
- [x] Unit test per shape: select single segment → expected Tier-2 ops enabled, others disabled with correct tooltip
- [x] Multi-select test: `{plateau, step}` → intersection empty → all Tier-2 disabled
- [x] `npm test` and `npm run build` pass

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "UI-006: shape-gating logic for Tier-2 buttons"` ← hook auto-moves this file to `done/` on commit
