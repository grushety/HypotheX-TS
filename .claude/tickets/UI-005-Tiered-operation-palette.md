# UI-005 — Tiered operation palette

**Status:** [ ] Done
**Depends on:** UI-004, OP-001, OP-002, OP-003; later OP-010..013, OP-020..026, OP-030..033

---

## Goal

Render the operation palette in **four visually distinct tier rows**:
- **Tier 0** — 3 structural ops (edit_boundary, split, merge); always visible, enabled on segment selection
- **Tier 1** — 9 label-agnostic atoms (scale, offset, mute_zero, time_shift, reverse_time, resample, suppress, replace_from_library, add_uncertainty); always visible, enabled when one segment selected
- **Tier 2** — up to 9 per-shape ops; enabled only when active segment's shape matches (gating done by UI-006)
- **Tier 3** — 4 composite ops (decompose, align_warp, enforce_conservation, aggregate); separate multi-segment toolbar; align_warp requires ≥2 segments

**Why:** The tiered palette is the user-facing surface of HypotheX-TS's core interaction contribution (strongest IUI differentiator). Making the structure visible in the UI is as important as implementing the underlying ops.

---

## Acceptance Criteria

- [ ] `frontend/src/components/palette/OperationPalette.vue` renders four tier rows stacked vertically with labels ("Tier 0: structural", "Tier 1: basic atoms", "Tier 2: shape-specific", "Tier 3: composite")
- [ ] `OperationButton.vue` subcomponent renders one op button with icon, label, enabled/disabled state
- [ ] Tier 0 (3 buttons) and Tier 1 (9 buttons) render always; disabled state when no selection
- [ ] Tier 2 row shows 5–9 buttons depending on active segment's shape (UI-006 gating)
- [ ] Tier 3 row rendered in a separate toolbar component `MultiSegmentToolbar.vue`; enables align_warp only when ≥2 segments selected
- [ ] Button click emits `op-invoked` with `{tier, op_name}`; parent route dispatches to backend via API client
- [ ] Loading state (spinner on button) while op is pending
- [ ] Keyboard: Alt+0/1/2/3 focuses respective tier row; arrow keys navigate within row; Enter invokes
- [ ] aria-label on every button; tier row is `role="toolbar"`
- [ ] Fixture test: select plateau → Tier 2 shows 5 plateau ops; select cycle → shows 7; multi-select different shapes → Tier 2 all disabled with intersection tooltip
- [ ] `npm test` and `npm run build` pass

## Definition of Done
- [ ] Run `test-writer` agent — tier rendering, gating, multi-select intersection, keyboard all tested
- [ ] Run `code-reviewer` agent — no blocking issues; no op-to-tier mapping duplicated across files (single source: `operationCatalog.js`)
- [ ] `git commit -m "UI-005: tiered operation palette (Tier 0/1/2/3)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
