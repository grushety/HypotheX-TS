# HTS-103 — AuditLogPanel replaces HistoryPanel in bottom strip

**Status:** [x] Done
**Depends on:** HTS-101

---

## Goal

Replace the `HistoryPanel` currently rendered inside the `.history-strip` `<details>` in `BenchmarkViewerPage.vue` with the full `AuditLogPanel` from UI-015. The new panel has the columns and filters required for downstream user-study analysis (tier / rule_class / compensation_mode / plausibility_badge / constraint_residual) and proper CSV+JSON export per the column schema.

`HistoryPanel` is currently the only thing populating the audit strip; deleting it would lose the existing summary view, so this ticket keeps a thin summary header and lets `AuditLogPanel` own the table.

---

## Acceptance Criteria

- [x] Inside the `.history-strip` `<details>` in `BenchmarkViewerPage.vue`, replace `<HistoryPanel/>` with `<AuditLogPanel/>`
- [x] `AuditLogPanel` props: `historyEntries` (existing computed), `labelChipBus` (the OP-041 frontend bus instance from HTS-101) *(panel takes `events` + `session`; subscribes to `labelChipBus` internally — same data the old `historyEntries` computed produced)*
- [x] The panel subscribes to `labelChipBus` on mount and unsubscribes on unmount; on every chip event it appends a row with the new fields *(unchanged from UI-015 implementation)*
- [x] Existing audit events (Tier-0 boundary edits, label updates, suggestion accept/override) appear in the panel with `—` for fields they don't populate, per the UI-015 spec
- [x] Filter dropdowns work: tier (0/1/2/3), rule_class, plausibility colour, op name; date/time range pickers work *(unchanged from UI-015)*
- [x] CSV and JSON export buttons (`Export CSV`, `Export JSON`) preserve all columns including nested `constraint_residual` for JSON; CSV serialises residual as a JSON-string in one cell *(unchanged from UI-015)*
- [x] Row click opens detail panel with full op payload (params + full residual breakdown) *(unchanged from UI-015)*
- [x] The existing `Export Log` button on `HistoryPanel` is removed (the new panel owns export); `handleExportLog` is renamed or repurposed accordingly *(removed `handleExportLog` and the `createInteractionLogExport`/`downloadInteractionLogExport` imports)*
- [x] `HistoryPanel` is NOT deleted — it stays in the codebase as the chip-with-status summary used elsewhere — but the import in `BenchmarkViewerPage.vue` is removed
- [x] `PlausibilityBadge` continues to render inside `HistoryPanel` if `HistoryPanel` is mounted elsewhere; the new `AuditLogPanel` has its own plausibility column per UI-015
- [x] Existing tests stay green; integration test verifies a Tier-2 op produces a row with non-null tier + rule_class + residual
- [x] `npm test` and `npm run build` pass

---

## Definition of Done
- [x] Run `tester` agent — all tests pass *(subagent budget exhausted; ran `npm test`: 694/694, `npm run build` clean)*
- [x] Run `code-reviewer` agent — no blocking issues *(subagent budget exhausted; self-reviewed against CLAUDE.md — see Result Report)*
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "HTS-103: AuditLogPanel replaces HistoryPanel in bottom strip"`

---

## Result Report

**What shipped**
- `BenchmarkViewerPage.vue`: replaced `<HistoryPanel/>` with `<AuditLogPanel :events="auditEvents" :session="sessionPanelState"/>` inside the `.history-strip` `<details>`. Removed the `handleExportLog` function plus its `createInteractionLogExport` / `downloadInteractionLogExport` imports (the new panel owns export). Removed the unused `createHistoryEntries` import + computed.
- `frontend/src/lib/audit/auditEvents.js`: extended `createAuditEvent` to carry two new optional nullable fields, `chip` and `constraintResidual`. `createOperationAuditEvent` now passes `result.chip` / `result.constraintResidual` (or context fallbacks) into the event so the panel can render Tier-2 op rows with populated `tier` / `ruleClass` / `residual`.
- `frontend/src/lib/audit/createAuditLogPanelState.js`: `makeRow` now reads `event.chip` (in addition to the existing chip-by-sequence map) and `event.constraintResidual` (in addition to the existing warnings-array path). The chip lookup is union, not replacement — UI-015's chip-bus subscription continues to feed rows the same way it always has; HTS-103 just lets HTS-101's response-attached chips reach the same rows without needing a sequence match.
- HTS-101's `applyInvokeResponse` now passes `chip: response.label_chip` and `constraintResidual: response.constraint_residual` into the audit-event creator so the new pass-through fires.
- New file `frontend/src/lib/audit/auditLogPanelIntegration.test.js`: 2 tests pinning the contract — Tier-2 op with chip+residual produces a row with non-null tier (from chip), ruleClass (PRESERVED), preShape/postShape, plausibilityBadge (green from confidence 0.92), and constraintResidual; Tier-0 boundary-edit row still has tier=0 from the action-type lookup and null chip/residual.
- Updated `auditEvents.test.js` deepEqual snapshot to include the two new nullable fields.

**Chip / residual on the event (load-bearing)**
The original UI-015 panel design assumed chips arrive via a separate `labelChipBus` subscription and are matched to events by `sequence`. HTS-101 publishes chips to the bus *and* attaches them to the corresponding audit event. The panel now reads both paths (event-attached chip OR bus-published chip indexed by sequence) so future tickets adding chip carriers can choose either pattern. The same is true for `constraintResidual`: read either from `event.constraintResidual` (HTS-101 path) or from `event.warnings` (legacy UI-015 path).

**Self-review against CLAUDE.md**
- *No fetch in Vue components*: not changed. ✓
- *Pure libs are pure*: `createAuditLogPanelState.js` and `auditEvents.js` remain pure. ✓
- *Audit log non-optional*: still appended on every op call. ✓
- *Frozen DTO / segment-not-chunk*: not introduced. ✓
- *Backwards-compatibility hack rule*: the chip/residual fields default to `null` so existing event consumers that don't read them are unaffected; the deepEqual test was updated to reflect the schema bump. No backwards-compat shims left over.

**Tests**
- `npm test`: 694/694 pass (2 new).
- `npm run build`: 87 modules transformed, 565 ms, 188 kB / 62 kB gzipped.

**Subagent budget**
Subagents (`tester`, `code-reviewer`) remain unavailable. Used direct `npm test` + `npm run build` + the self-review checklist.
