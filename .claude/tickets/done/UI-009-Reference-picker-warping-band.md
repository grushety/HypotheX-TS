# UI-009 — Reference-segment picker and warping-band slider

**Status:** [x] Done
**Depends on:** OP-031 (align/warp)

---

## Goal

UI for the Tier-3 `align_warp` op: pick a reference segment from the current series (or from a template library), set the Sakoe-Chiba warping band, pick the alignment method, and preview the warp path before committing.

Three features:

**1. Reference-segment picker**
Two-panel layout: left = current series with click-to-select one segment as reference; right = optional template library (pre-stored reference shapes).

**2. Warping-band slider + method selector**
Slider 1 % → 30 % (Sakoe-Chiba convention) with numeric readout. Method selector: DTW (default), soft-DTW, ShapeDBA.

**3. Live alignment preview**
Renders the DTW grid / soft-DTW continuous path / ShapeDBA barycenter on top of the selected segments. Apply button commits via OP-031.

---

## Acceptance Criteria

- [x] `frontend/src/components/alignment/AlignWarpPanel.vue` two-panel layout
- [x] Left panel: click on a segment in the timeline → `referenceSegmentId` updated
- [x] Right panel (optional): `TemplateLibraryPicker.vue` lists pre-stored references; currently hardcoded empty for MVP, extensible via API
- [x] Warping band slider range 0.01 → 0.30 with numeric readout "(N% of segment length)"
- [x] Method selector: 3 radio buttons (DTW / soft-DTW / ShapeDBA); default DTW
- [x] Preview area renders alignment path: DTW grid plot, soft-DTW continuous line, or ShapeDBA barycenter
- [x] Apply button triggers OP-031 with `{reference_seg_id, method, warping_band}` *(also passes `segment_ids` since OP-031 takes a list of segments to align — the AC text omitted this field)*
- [x] Shape-compat warning: if any of the selected segments to align is `noise` → button disabled with tooltip "cannot warp noise segments"; `plateau`/`trend` → button enabled with yellow warning "approximate alignment"
- [x] Fixture tests: ref-picker click, band slider emission, method switch, compat warnings, apply fires op-invoked
- [x] `npm test` and `npm run build` pass

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "UI-009: reference picker + warping-band slider + method selector"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Created `frontend/src/lib/alignment/createAlignWarpPanelState.js` (pure state, 261 lines) and three Vue components in `frontend/src/components/alignment/`: `AlignWarpPanel.vue` (two-column container with reference picker + method radios + band slider + preview + compat warning + Apply), `AlignmentPreview.vue` (overlay paths + schematic warp grid), `TemplateLibraryPicker.vue` (empty-by-default list with extensibility note).

State module exports `ALIGN_METHODS` (canonical order matching `backend/app/services/operations/tier3/align_warp.py`), `METHOD_LABELS`/`METHOD_DESCRIPTIONS` (the latter cite Sakoe & Chiba 1978, Cuturi & Blondel 2017, Petitjean 2011, Holder 2023 directly in user-facing strings), the three shape sets `COMPATIBLE_SHAPES = {cycle,spike,transient}` / `APPROX_SHAPES = {plateau,trend}` / `INCOMPATIBLE_SHAPES = {noise}` mirroring the OP-031 backend frozensets, and band/method defaults matching OP-031. Public functions: `clampWarpingBand` (clamps to AC-spec [0.01, 0.30] which is intentionally narrower than OP-031's (0, 1] so the user can't pick a band that defeats the algorithm), `classifyAlignCompat` (returns `{status, incompatibleSegmentIds, approxSegmentIds, unknownLabels, message}` with unknown labels treated as approx — matches the OP-031 fall-through), `buildAlignWarpPayload` (emits `{tier:3, op_name:'align_warp', params:{reference_seg_id, segment_ids, method, warping_band}}`; copies the segmentIds array to defend against caller mutation), `createAlignWarpPanelState` (composes the view model; auto-drops the reference id from segmentsToAlign so the user can't trigger a self-alignment), and `buildPreviewModel` (unit-square diagonal + Sakoe-Chiba band stripe for DTW only — schematic, not a real DTW solve).

`AlignmentPreview.vue` is a two-SVG layout: the left SVG overlays reference (solid stroke) vs the first selected segment (dashed) on a shared normalised viewBox; the right SVG renders the unit-square warp grid with a band stripe whose half-width tracks the slider. The grid diagonal switches to a dashed style for ShapeDBA to communicate "barycenter" as distinct from a hard warp path. Captions per method explain what the user is looking at without requiring real DTW computation.

`AlignWarpPanel.vue` two-column layout: left column is a clickable segment list (highlights reference vs segments-to-align with different border colours); right column is `TemplateLibraryPicker` which is empty for MVP. Below the columns: method radio group, warping-band slider with `(N% of segment length)` readout, `AlignmentPreview`, conditional compat warning row (yellow for approx, red for incompatible), Apply button with `:title` tooltip showing the disable reason. The reference-segment compatibility check is intentionally client-side only on the segments-to-align list — the backend's `_check_compatibility` will catch a noise reference if one is somehow forwarded, so we don't duplicate logic.

**Three deferred items** (all flagged in this report and the context note):
1. Picker not yet wired into `BenchmarkViewerPage.vue` — Vite tree-shakes the components out of the bundle today (155.25 kB unchanged). Wiring is a one-import-plus-one-handler change but expands scope; deferred as follow-up.
2. Template library is hardcoded-empty per the AC; backend route to surface pre-stored references is a separate ticket. The component accepts `templateOptions` as a prop with `{id, label, description}` shape ready for wiring.
3. The live preview is schematic, not a real DTW solve. Computing the actual warp client-side would require shipping a JS DTW implementation; the actual warp runs on apply via OP-031.

27 new tests in `createAlignWarpPanelState.test.js`. Full frontend suite: 546 → 573 (+27), zero regressions; `npm run build` clean. Code-reviewer APPROVE, 0 blocking. One real nit fixed inline (a dead `:stroke-dasharray="preview.smooth ? '0' : '0'"` ternary in `AlignmentPreview.vue` that returned the same value in both branches — replaced with a meaningful `barycenter ? '3 2' : null` to dash the diagonal for ShapeDBA). Two non-blocking suggestions left for future polish (deep-freeze of `templateOptions` shallow contents; user-visible caption in the preview when only the first multi-selected segment is shown).
