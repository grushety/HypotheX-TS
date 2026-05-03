# HTS-101 — Frontend op dispatcher (Tier 1/2 + picker-free Tier-3)

**Status:** [ ] Done
**Depends on:** HTS-100

---

## Goal

Replace the `"... not yet implemented"` branch of `handleOpInvoked` in `BenchmarkViewerPage.vue` with a real dispatcher that calls `POST /api/operations/invoke` and applies the result to local state.

Scope: every op that does NOT require a picker. The four picker-bound ops (`replace_from_library`, `decompose`, `align_warp`, and `suppress` on a gap-heavy segment) keep returning a "picker pending" feedback message; HTS-104 / HTS-105 / HTS-106 wire them.

After this ticket, clicking any Tier-1 amplitude/time/stochastic atom (except `replace_from_library`), any Tier-2 per-shape op (`AmplitudeSlider`-driven ops included via UI-016's `groupTier2Controls`), Tier-3 `enforce_conservation`, and Tier-3 `aggregate` produces a real backend round-trip + audit event + sample update.

---

## Acceptance Criteria

- [ ] New API client method `invokeOperation({tier, op_name, params, ...})` in `frontend/src/services/api/` (either extend `benchmarkApi.js` or create a new `operationsApi.js`) calling `POST /api/operations/invoke`
- [ ] Frontend op-catalog mapping that, for each op, builds the request `params` from the selected segment + UI input (sliders, defaults, etc.). Lives in a new pure module `frontend/src/lib/operations/buildInvokeRequest.js` so it is unit-testable.
- [ ] `OperationPalette` op-invoked event payload widened from `{tier, op_name}` to `{tier, op_name, params}`. `AmplitudeSlider` already emits `params: {alpha}` per UI-016 — verify the parent now propagates it.
- [ ] `handleOpInvoked` rewritten to dispatch:
  - Tier 0 → existing path (unchanged)
  - Tier 1 except `replace_from_library`: build params, call `invokeOperation`, apply result
  - Tier 1 `suppress`: when selected segment is gap-heavy (read `gapInfo` for that segment) fall through to `"GapFillPicker pending"` feedback; otherwise dispatch with default strategy
  - Tier 2 (all per-shape ops): dispatch using params from the slider / op-card defaults
  - Tier 3 `enforce_conservation` and `aggregate`: dispatch normally
  - Tier 3 `decompose` and `align_warp`: feedback `"<op_name> picker pending"`
- [ ] Result handling:
  - `values` → splice into `sample.values` at `[segment.start, segment.end]` for segment-bounded ops; replace whole series for whole-series ops
  - `label_chip` → publish to `labelChipBus` (the OP-041 frontend bus that AuditLogPanel and PredictedLabelChip subscribe to in later tickets)
  - `aggregate_result` → store on a new `aggregateResult` ref so HTS-102 can render it; for now show a one-line feedback summary
  - `constraint_residual` → set on the existing `operationConstraintResult` so the warning panel updates; HTS-102 binds the budget bar
  - Append an audit event of kind `operation` carrying tier, op_name, params, audit_id, label_chip
- [ ] Backend errors surfaced as user-readable feedback (the route's 400/404/422 messages)
- [ ] Pending-state: `pendingOpName` ref already exists; set it for the duration of the call
- [ ] Tests in `frontend/src/lib/operations/buildInvokeRequest.test.js` covering: one Tier-1 op with slider params, one Tier-2 op with shape gating, one Tier-3 picker-free op, gap-heavy `suppress` falling through to picker-pending, and unknown op throwing
- [ ] `npm test` and `npm run build` pass

---

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "HTS-101: frontend op dispatcher for Tier 1/2 + picker-free Tier-3"`
