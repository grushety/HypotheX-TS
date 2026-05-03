# HTS-103 — AuditLogPanel replaces HistoryPanel in bottom strip

**Status:** [ ] Done
**Depends on:** HTS-101

---

## Goal

Replace the `HistoryPanel` currently rendered inside the `.history-strip` `<details>` in `BenchmarkViewerPage.vue` with the full `AuditLogPanel` from UI-015. The new panel has the columns and filters required for downstream user-study analysis (tier / rule_class / compensation_mode / plausibility_badge / constraint_residual) and proper CSV+JSON export per the column schema.

`HistoryPanel` is currently the only thing populating the audit strip; deleting it would lose the existing summary view, so this ticket keeps a thin summary header and lets `AuditLogPanel` own the table.

---

## Acceptance Criteria

- [ ] Inside the `.history-strip` `<details>` in `BenchmarkViewerPage.vue`, replace `<HistoryPanel/>` with `<AuditLogPanel/>`
- [ ] `AuditLogPanel` props: `historyEntries` (existing computed), `labelChipBus` (the OP-041 frontend bus instance from HTS-101)
- [ ] The panel subscribes to `labelChipBus` on mount and unsubscribes on unmount; on every chip event it appends a row with the new fields
- [ ] Existing audit events (Tier-0 boundary edits, label updates, suggestion accept/override) appear in the panel with `—` for fields they don't populate, per the UI-015 spec
- [ ] Filter dropdowns work: tier (0/1/2/3), rule_class, plausibility colour, op name; date/time range pickers work
- [ ] CSV and JSON export buttons (`Export CSV`, `Export JSON`) preserve all columns including nested `constraint_residual` for JSON; CSV serialises residual as a JSON-string in one cell
- [ ] Row click opens detail panel with full op payload (params + full residual breakdown)
- [ ] The existing `Export Log` button on `HistoryPanel` is removed (the new panel owns export); `handleExportLog` is renamed or repurposed accordingly
- [ ] `HistoryPanel` is NOT deleted — it stays in the codebase as the chip-with-status summary used elsewhere — but the import in `BenchmarkViewerPage.vue` is removed
- [ ] `PlausibilityBadge` continues to render inside `HistoryPanel` if `HistoryPanel` is mounted elsewhere; the new `AuditLogPanel` has its own plausibility column per UI-015
- [ ] Existing tests stay green; integration test verifies a Tier-2 op produces a row with non-null tier + rule_class + residual
- [ ] `npm test` and `npm run build` pass

---

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "HTS-103: AuditLogPanel replaces HistoryPanel in bottom strip"`
