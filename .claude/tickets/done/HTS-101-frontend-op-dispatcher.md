# HTS-101 — Frontend op dispatcher (Tier 1/2 + picker-free Tier-3)

**Status:** [x] Done
**Depends on:** HTS-100

---

## Goal

Replace the `"... not yet implemented"` branch of `handleOpInvoked` in `BenchmarkViewerPage.vue` with a real dispatcher that calls `POST /api/operations/invoke` and applies the result to local state.

Scope: every op that does NOT require a picker. The four picker-bound ops (`replace_from_library`, `decompose`, `align_warp`, and `suppress` on a gap-heavy segment) keep returning a "picker pending" feedback message; HTS-104 / HTS-105 / HTS-106 wire them.

After this ticket, clicking any Tier-1 amplitude/time/stochastic atom (except `replace_from_library`), any Tier-2 per-shape op (`AmplitudeSlider`-driven ops included via UI-016's `groupTier2Controls`), Tier-3 `enforce_conservation`, and Tier-3 `aggregate` produces a real backend round-trip + audit event + sample update.

---

## Acceptance Criteria

- [x] New API client method `invokeOperation({tier, op_name, params, ...})` in `frontend/src/services/api/` (either extend `benchmarkApi.js` or create a new `operationsApi.js`) calling `POST /api/operations/invoke`
- [x] Frontend op-catalog mapping that, for each op, builds the request `params` from the selected segment + UI input (sliders, defaults, etc.). Lives in a new pure module `frontend/src/lib/operations/buildInvokeRequest.js` so it is unit-testable.
- [x] `OperationPalette` op-invoked event payload widened from `{tier, op_name}` to `{tier, op_name, params}`. `AmplitudeSlider` already emits `params: {alpha}` per UI-016 — verify the parent now propagates it.
- [x] `handleOpInvoked` rewritten to dispatch:
  - Tier 0 → existing path (unchanged)
  - Tier 1 except `replace_from_library`: build params, call `invokeOperation`, apply result
  - Tier 1 `suppress`: when selected segment is gap-heavy (read `gapInfo` for that segment) fall through to `"GapFillPicker pending"` feedback; otherwise dispatch with default strategy
  - Tier 2 (all per-shape ops): dispatch using params from the slider / op-card defaults
  - Tier 3 `enforce_conservation` and `aggregate`: dispatch normally
  - Tier 3 `decompose` and `align_warp`: feedback `"<op_name> picker pending"`
- [x] Result handling:
  - `values` → splice into `sample.values` at `[segment.start, segment.end]` for segment-bounded ops; replace whole series for whole-series ops
  - `label_chip` → publish to `labelChipBus` (the OP-041 frontend bus that AuditLogPanel and PredictedLabelChip subscribe to in later tickets)
  - `aggregate_result` → store on a new `aggregateResult` ref so HTS-102 can render it; for now show a one-line feedback summary
  - `constraint_residual` → set on the existing `operationConstraintResult` so the warning panel updates; HTS-102 binds the budget bar
  - Append an audit event of kind `operation` carrying tier, op_name, params, audit_id, label_chip
- [x] Backend errors surfaced as user-readable feedback (the route's 400/404/422 messages)
- [x] Pending-state: `pendingOpName` ref already exists; set it for the duration of the call
- [x] Tests in `frontend/src/lib/operations/buildInvokeRequest.test.js` covering: one Tier-1 op with slider params, one Tier-2 op with shape gating, one Tier-3 picker-free op, gap-heavy `suppress` falling through to picker-pending, and unknown op throwing
- [x] `npm test` and `npm run build` pass

---

## Definition of Done
- [x] Run `tester` agent — all tests pass *(subagent budget exhausted; ran `npm test`: 688/688 frontend, `npm run build` succeeds; backend `pytest tests/routes/test_operations_invoke.py`: 12/12)*
- [x] Run `code-reviewer` agent — no blocking issues *(subagent budget exhausted; self-reviewed against CLAUDE.md — see Result Report)*
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "HTS-101: frontend op dispatcher for Tier 1/2 + picker-free Tier-3"`

---

## Result Report

**What shipped**
- `frontend/src/services/api/operationsApi.js` — `invokeOperation(request, fetchImpl=fetch)` POSTs to `/api/operations/invoke`. Mirrors the existing `benchmarkApi.js` error-handling pattern (`readJsonResponse` lifts `payload.error` from 4xx responses into `Error.message`).
- `frontend/src/lib/operations/buildInvokeRequest.js` — pure module that returns either `{ kind: 'request', body }` (dispatch) or `{ kind: 'picker-pending', message }` (HTS-104/105/106 will wire the pickers). Holds three sets — `TIER1_OPS`, `TIER2_OPS`, `TIER3_OPS` — that mirror the backend's `_TIER1_REGISTRY` / `_TIER2_REGISTRY` plus the Tier-3 op list. Unknown op_names throw `UnknownOpError` synchronously so the user sees an immediate error rather than a backend round-trip 400.
- `frontend/src/lib/operations/buildInvokeRequest.test.js` — 9 tests: Tier-1 with slider params, Tier-2 shape op, Tier-3 picker-free aggregate, gap-heavy suppress → picker-pending, non-gap suppress → dispatch, picker-bound trio (replace_from_library + decompose + align_warp), unknown-op throw, mute_zero default fill, slider-commit alias `amplify_amplitude`.
- `frontend/src/views/BenchmarkViewerPage.vue` — `handleOpInvoked` now widens `{tier, op_name}` → `{tier, op_name, params = {}}` and routes Tier 1/2/3 through a new `dispatchTier123Op` helper. New `applyInvokeResponse` splices `response.values` into `sample.values[seg.start..seg.end]`, publishes `response.label_chip` to `labelChipBus`, surfaces `response.aggregate_result` on a new `aggregateResult` ref, lifts `response.constraint_residual` onto the existing `operationConstraintResult`, and appends an `operation` audit event. New `selectedSegmentGapInfo` computed feeds `gapInfo` into `buildInvokeRequest` so gap-heavy `suppress` routes to the picker-pending message.
- `backend/app/services/operations/invoke_service.py` — added `'amplify_amplitude'` alias to `_TIER2_REGISTRY` so the UI-016 slider commit (which emits `op_name: 'amplify_amplitude'` for `cycle_amplify` / `cycle_damp`) round-trips correctly.

**Slider-commit alias contract (load-bearing)**
The UI-016 slider unifies amplify+dampen as a single op with signed `α`, emitting `op_name: 'amplify_amplitude'` (the *backend function name*) instead of either palette name. The backend registry now holds both palette keys (`cycle_amplify` / `cycle_damp` for the buttons users see in tests) AND the slider-commit alias (`amplify_amplitude`). Future slider configs in `sliderOps.js` must register their `commitOpName` in `_TIER2_REGISTRY` if it differs from the palette `op_name`.

**Picker-pending sentinel pattern (load-bearing)**
`buildInvokeRequest` returns a `{kind: 'picker-pending', message}` sentinel for the four picker-bound ops instead of throwing or returning null. The dispatcher reads the `kind` discriminant once and either fires the request or surfaces the message — no error path bleeding into the success path. HTS-104 / HTS-105 / HTS-106 will replace the sentinel with a real picker invocation. Until then the user sees clear "X: picker pending" feedback.

**Self-review against CLAUDE.md**
- *No fetch in Vue components*: `BenchmarkViewerPage.vue` calls `invokeOperation` from `services/api/operationsApi.js`. ✓
- *Pure libs are pure*: `buildInvokeRequest.js` has no Vue, no fetch, no DOM — easy to unit-test. ✓
- *Audit log non-optional*: every successful op call appends an `operation` audit event with `params`. ✓
- *Frozen DTOs / segment-not-chunk*: not introduced (this ticket is wiring). ✓

**Tests**
- `npm test`: 688/688 pass.
- `npm run build`: 78 modules transformed, 619 ms, 163 kB / 55 kB gzipped.
- Backend `pytest tests/routes/test_operations_invoke.py`: 12/12 still pass (only the 2 pre-existing unrelated failures remain in the full backend suite).

**Subagent budget**
Subagents (`tester`, `code-reviewer`) remain unavailable. Used direct `npm test` + `npm run build` + the self-review checklist.
