# UI-014 — Semantic-layer panel (domain pack selector)

**Status:** [ ] Done
**Depends on:** SEG-021, SEG-022, SEG-023 (domain packs)

---

## Goal

Side panel that lets the user choose an active domain pack (hydrology / seismo-geodesy / remote-sensing / none / custom-upload). When active, shape chips in UI-004 show an overlaid secondary semantic-label text derived from pack detectors.

---

## Acceptance Criteria

- [ ] `frontend/src/components/semantic/SemanticLayerPanel.vue` side-panel component
- [ ] Dropdown selector: 4 built-in packs + "None" + "Custom upload"
- [ ] Pack info panel displays the list of semantic labels with their shape primitive mappings (read from pack YAML)
- [ ] When active, pack detectors run on each segment (via API call) and attach semantic labels; UI-004 chip sub-text updates reactively
- [ ] Pack switch is non-destructive: shape labels remain unchanged; only semantic-label overlay changes
- [ ] Custom upload accepts YAML file; validated against schema before activating; on validation failure shows inline error with line number
- [ ] Current pack persists in session storage; reloads on page refresh
- [ ] User-defined labels shadow pack labels per-project (per [[_project HypotheX-TS/HypotheX-TS - Implementation Plan]] §8.4); visual indicator on shadowed labels
- [ ] Fixture tests: hydrology pack loads on streamflow fixture, baseflow/stormflow labels appear; switch to "None" clears semantic-label overlay; custom YAML validates + applies; invalid YAML shows line-number error
- [ ] `npm test` and `npm run build` pass

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "UI-014: semantic-layer panel with 4 packs + custom upload"` ← hook auto-moves this file to `done/` on commit
