# UI-015 — Audit log panel extension (tiered ops)

**Status:** [ ] Done
**Depends on:** OP-041 (label chip events), existing audit log infrastructure

---

## Goal

Extend the audit log panel to capture and display the new per-op fields: tier, compensation mode, plausibility badge, pre/post shape label, rule class, constraint residual.

**Why:** The audit log is the core data export for downstream user-study analysis (bias metrics per [[_project HypotheX-TS/HypotheX-TS - Evaluation]]). Without tier and rule-class fields, the exploration-pattern metrics in UI-005 + UI-013 cannot be computed from the log.

---

## Acceptance Criteria

- [ ] `frontend/src/components/audit/AuditLogPanel.vue` extended with additional columns
- [ ] Columns: `timestamp | tier | op | segment_id | pre_shape → post_shape | rule_class | compensation_mode | plausibility_badge | constraint_residual`
- [ ] Filter dropdowns for: tier (0/1/2/3), rule class, plausibility badge colour, op name
- [ ] Date/time range filter (from/to pickers)
- [ ] Export to CSV and JSON preserves all columns including nested `constraint_residual` dict
- [ ] Existing Tier-0 `edit_boundary` ops display correctly; new-field columns show "—" for ops that do not populate them
- [ ] Log subscribes to `label_chip` event bus topic (from OP-041); appends row per event
- [ ] Row click opens detail panel showing full op payload (parameters, full residual breakdown)
- [ ] Undo stack synced with log (undo removes the last row; re-applying adds it back with new timestamp)
- [ ] Fixture test: apply one op per tier → all rows present with correct fields; filter by Tier 2 → only Tier-2 rows visible; CSV export round-trips all fields
- [ ] `npm test` and `npm run build` pass

## Definition of Done
- [ ] Run `test-writer` agent — new columns populated, filters work, export round-trips, undo sync
- [ ] Run `code-reviewer` agent — no blocking issues; CSV export escapes correctly (no broken rows with commas in fields)
- [ ] `git commit -m "UI-015: audit log extension for tiered ops"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
