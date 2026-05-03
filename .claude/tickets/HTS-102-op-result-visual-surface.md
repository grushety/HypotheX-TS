# HTS-102 — Op-result visual surface (ConstraintBudgetBar + CompensationModeSelector + PredictedLabelChip)

**Status:** [ ] Done
**Depends on:** HTS-101

---

## Goal

Now that Tier-1/2/3 ops actually run and return `constraint_residual` + `label_chip` + `validation`, surface them visually in the main page. Three components are built and tested but unmounted today: `ConstraintBudgetBar` (UI-010), `CompensationModeSelector` (UI-011), and `PredictedLabelChip` (UI-013). This ticket mounts all three in `BenchmarkViewerPage.vue`.

`PlausibilityBadge` (UI-012) is already inside `HistoryPanel` per `context.md` — verify it now receives populated `constraintResidual` / `plausibilityRange` / `plausibilityManifold` from the audit events HTS-101 emits.

---

## Acceptance Criteria

- [ ] `ConstraintBudgetBar` mounted in the right column, immediately above `OperationPalette`, bound to the `constraint_residual` of the most recent op result. Hidden when there is no residual to show.
- [ ] `CompensationModeSelector` mounted as an inline row inside the op-card area (visible when the user has selected a Tier-2 op whose op_category is in {plateau, trend, step, transient} AND the active domain hint is in {hydrology, seismo-geodesy}). The selected mode is forwarded into the next `invokeOperation` call as `compensation_mode`.
- [ ] When `isCompensationRequired` is true and `hasExplicitChoice` is false, the op button is disabled with the AC-spec hint message; once the user picks a mode, the button re-enables. (Reuses the gating already implemented in UI-011.)
- [ ] `PredictedLabelChip` mounted inside `TimelineViewer` (or as a child of the chart panel positioned absolutely above the active segment). It subscribes to `labelChipBus` on mount, unsubscribes on unmount.
- [ ] Chip user actions:
  - **Accept** → emit `chip-accepted` upward; parent updates the segment label in `sample.segments` with the predicted label; appends an `accept` audit event.
  - **Override** → opens `ShapePicker`; on pick, parent updates label to the picked one and appends an `override` audit event.
  - **Undo** → reverts the most recent op (parent restores the previous `sample.values` from a small undo stack, max depth 10) and appends an `undo` audit event.
  - **Auto-accept timer**: defaults to 5000 ms, configurable via a constant in `createLabelChipState.js`. On timeout, dismiss + accept fire together (per UI-013 contract).
- [ ] Confirm `HistoryPanel` continues to render `PlausibilityBadge` correctly for the new audit events (no regression). If the badge data path is broken because the new events don't carry the expected fields, fix the audit-event creator (not the badge).
- [ ] Existing tests stay green; one new integration test in `BenchmarkViewerPage.test.js` (or a new sibling) asserting that after a fake op result, the budget bar renders, the chip subscribes, and the compensation selector becomes visible for a hydrology plateau op.
- [ ] `npm test` and `npm run build` pass

---

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "HTS-102: op-result visual surface (budget bar + compensation + label chip)"`
