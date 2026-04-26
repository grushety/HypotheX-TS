# UI-009 — Reference-segment picker and warping-band slider

**Status:** [ ] Done
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

- [ ] `frontend/src/components/alignment/AlignWarpPanel.vue` two-panel layout
- [ ] Left panel: click on a segment in the timeline → `referenceSegmentId` updated
- [ ] Right panel (optional): `TemplateLibraryPicker.vue` lists pre-stored references; currently hardcoded empty for MVP, extensible via API
- [ ] Warping band slider range 0.01 → 0.30 with numeric readout "(N% of segment length)"
- [ ] Method selector: 3 radio buttons (DTW / soft-DTW / ShapeDBA); default DTW
- [ ] Preview area renders alignment path: DTW grid plot, soft-DTW continuous line, or ShapeDBA barycenter
- [ ] Apply button triggers OP-031 with `{reference_seg_id, method, warping_band}`
- [ ] Shape-compat warning: if any of the selected segments to align is `noise` → button disabled with tooltip "cannot warp noise segments"; `plateau`/`trend` → button enabled with yellow warning "approximate alignment"
- [ ] Fixture tests: ref-picker click, band slider emission, method switch, compat warnings, apply fires op-invoked
- [ ] `npm test` and `npm run build` pass

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "UI-009: reference picker + warping-band slider + method selector"` ← hook auto-moves this file to `done/` on commit
