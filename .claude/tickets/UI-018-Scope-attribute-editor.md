# UI-018 — Scope attribute editor

**Status:** [ ] Done
**Depends on:** [[_project HypotheX-TS/HypotheX-TS - Formal Definitions]] §2 (scope attribute)

---

## Goal

Per-segment editor for the `scope` attribute — the window context used to disambiguate cycle vs transient and to set domain hints on individual segments. Exposes window size, sliding-vs-fixed mode, and domain hint. Editing scope triggers reclassification via OP-040 `RECLASSIFY_VIA_SEGMENTER`.

**Why:** Scope is a first-class segment attribute that affects classification (per [[_project HypotheX-TS/HypotheX-TS - Formal Definitions]] §2). Without a UI to edit it, the attribute is dead code; with it, users can fix edge cases where a short-scope view misreads a transient as cycle (or vice versa).

---

## Acceptance Criteria

- [ ] `frontend/src/components/scope/ScopeAttributeEditor.vue` dialog opened from a shape-chip context menu
- [ ] Fields:
  - `scope_window_size` (positive integer, samples; validated > 0)
  - `scope_mode` radio: `{fixed, sliding}`
  - `scope_reference` (timestamp picker, used only when `scope_mode == 'fixed'`)
  - `domain_hint` dropdown: `{hydrology, seismo-geodesy, remote-sensing, other, inherit from project}`
- [ ] On save, emits `scope-updated` event; parent dispatches API call that updates the segment and triggers OP-040 with `RECLASSIFY_VIA_SEGMENTER` rule
- [ ] Predicted new label shown via UI-013 chip after reclassification completes
- [ ] Audit log captures scope edit (UI-015) with pre/post scope values
- [ ] Default scope inherited from domain pack (UI-014): hydrology → sliding window 30 days; seismo-geodesy → fixed origin-time reference; remote-sensing → sliding window 1 year
- [ ] Invalid window_size (≤0 or > series length) disables Save button with inline error
- [ ] Fixture tests: open editor, change window_size, save → API call + UI-013 chip appears; invalid window blocked; domain-hint change triggers re-classify via SEG-008
- [ ] `npm test` and `npm run build` pass

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "UI-018: scope attribute editor"` ← hook auto-moves this file to `done/` on commit
