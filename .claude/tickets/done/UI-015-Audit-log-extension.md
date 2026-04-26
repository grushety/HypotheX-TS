# UI-015 — Audit log panel extension (tiered ops)

**Status:** [x] Done
**Depends on:** OP-041 (label chip events), existing audit log infrastructure

---

## Goal

Extend the audit log panel to capture and display the new per-op fields: tier, compensation mode, plausibility badge, pre/post shape label, rule class, constraint residual.

**Why:** The audit log is the core data export for downstream user-study analysis (bias metrics per [[_project HypotheX-TS/HypotheX-TS - Evaluation]]). Without tier and rule-class fields, the exploration-pattern metrics in UI-005 + UI-013 cannot be computed from the log.

---

## Acceptance Criteria

- [x] `frontend/src/components/audit/AuditLogPanel.vue` extended with additional columns
- [x] Columns: `timestamp | tier | op | segment_id | pre_shape → post_shape | rule_class | compensation_mode | plausibility_badge | constraint_residual`
- [x] Filter dropdowns for: tier (0/1/2/3), rule class, plausibility badge colour, op name
- [x] Date/time range filter (from/to pickers)
- [x] Export to CSV and JSON preserves all columns including nested `constraint_residual` dict
- [x] Existing Tier-0 `edit_boundary` ops display correctly; new-field columns show "—" for ops that do not populate them
- [x] Log subscribes to `label_chip` event bus topic (from OP-041); appends row per event
- [x] Row click opens detail panel showing full op payload (parameters, full residual breakdown)
- [x] Undo stack synced with log (undo removes the last row; re-applying adds it back with new timestamp)
- [x] Fixture test: apply one op per tier → all rows present with correct fields; filter by Tier 2 → only Tier-2 rows visible; CSV export round-trips all fields
- [x] `npm test` and `npm run build` pass

## Result Report

- 4 new files: `labelChipBus.js`, `createAuditLogPanelState.js`, `createAuditLogPanelState.test.js`, `AuditLogPanel.vue`
- 30 tests in audit lib (24 new + 6 pre-existing); 253 total frontend tests pass
- Code reviewer raised 2 blockers (date filter string comparison, `\r` in CSV) — both fixed
- Build: `vite build` passes, 132.96 kB JS bundle
- Component not yet mounted in `BenchmarkViewerPage.vue`; wire into `history-strip` when OP-041 is complete

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "UI-015: audit log extension for tiered ops"` ← hook auto-moves this file to `done/` on commit
