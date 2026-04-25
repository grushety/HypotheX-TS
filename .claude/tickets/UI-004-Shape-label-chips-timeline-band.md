# UI-004 — Shape-label chips and 7-shape timeline band

**Status:** [ ] Done
**Depends on:** UI-001, SEG-008

---

## Goal

Replace the current labeled segmentation band with a **7-shape-aware band**. Each segment renders as a colour-coded chip carrying its shape primitive `{plateau, trend, step, spike, cycle, transient, noise}`. Clicking a chip selects the segment and reveals its shape, confidence, and a one-line summary of its decomposition method.

Two features:

**1. Colour-coded chip per shape**
Distinct colour per shape (plateau=gray, trend=blue, step=orange, spike=red, cycle=teal, transient=purple, noise=light-gray). Tooltip: `shape | semantic_label? | confidence% | method`. Secondary semantic-label text shown below the chip when a domain pack is active (UI-014).

**2. Keyboard + click selection**
Click selects and publishes `segment_selected` event. Tab cycles through chips; Enter selects.

Wire into existing `TimelineViewer.vue` + `SegmentationOverlay.vue` (replacing the previous binary-label styling).

---

## Acceptance Criteria

- [ ] 7 colour tokens defined in `frontend/src/lib/viewer/shapeColors.js` with named export `SHAPE_COLORS`
- [ ] `ShapeChip.vue` component in `frontend/src/components/viewer/ShapeChip.vue` renders a single chip with colour + optional semantic-label sub-text
- [ ] `SegmentationOverlay.vue` renders one `ShapeChip` per segment with `shape`, `confidence`, `method` (from decomposition blob), `semantic_label` (optional)
- [ ] Tooltip content matches pattern `{shape} | {semantic?} | {conf_pct}% | {method}`
- [ ] Chip click emits `segment-selected` with `segment_id`
- [ ] Keyboard: Tab/Shift-Tab cycles through chips; Enter selects; visible focus ring
- [ ] Band scales correctly with zoom / brush (reuses existing x-scale from UI-001)
- [ ] Legend showing all 7 shapes rendered in a small legend component (`ShapeLegend.vue`); expandable to show semantic pack labels when pack active
- [ ] Fixture test: load synthetic series with one segment per shape → all 7 chips render with correct colour
- [ ] `npm test` and `npm run build` pass

## Definition of Done
- [ ] Run `test-writer` agent — chip rendering, tooltip content, keyboard navigation, click emission all tested
- [ ] Run `code-reviewer` agent — no blocking issues; no hard-coded colour strings outside `shapeColors.js`
- [ ] `git commit -m "UI-004: 7-shape chips and shape-aware timeline band"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
