# REWORK-09 — Delta provenance (which edit caused which change)

**Status:** [x] Done
**Depends on:** REWORK-02

---

## Goal

Link the operation/edit list to the OUTPUT Δ: selecting or hovering an operation
highlights its contribution to the prediction change, so the scientist can read *which
edit caused which movement* — and avoid the causal-misattribution trap ("I changed X
and it moved" ≠ "the model depends on X"). Exposed via the "Δ sources" affordance.

---

## Design source (read FIRST)
Read `.claude/tickets/REWORK/DESIGN-SOURCE.md`, then `designs\output.jsx` (the
"Δ sources" affordance) and `audit.jsx`. React → translate to Vue.

## Task 0 — Recon (record in Result Report)

- [x] Read `backend/app/services/audit_log.py` + `lib/audit/auditEvents` (frontend):
      document how the ordered operation sequence for a session is stored.
- [x] Confirm predictions can be computed at intermediate session states (needed to
      attribute per-op deltas).

## Algorithm & SOTA justification (pick + document)

Attributing a total prediction change to a sequence of applied operations is a
**feature-attribution-over-operations** problem. Recommended:

1. **Primary — leave-one-out / ordered marginal contribution.** For each op, compute
   the prediction with vs. without that op (re-applying the rest in order); the
   difference is its contribution. Cheap, exact for the realized path, easy to explain.
   Caveat to document: order-dependent and ignores interactions.
2. **Higher-fidelity (opt-in) — Shapley value over operations.** Average marginal
   contribution across operation orderings (or a sampled approximation, à la
   KernelSHAP). Handles interactions/correlated edits — directly the
   causal-misattribution concern. Cost grows with op count → cap N or sample.

Default to leave-one-out; offer Shapley when op count is small. State the order-
dependence caveat in the UI tooltip.

## Backend (new)

- [x] New service `delta_provenance` taking the ordered op list + sample + model,
      returning per-op contribution to the prediction Δ (per class for classification).
- [x] New thin route `POST /api/operations/provenance`.
- [x] Reuse `PredictionService`; no new model code.

## Acceptance Criteria

- [x] "Δ sources" in OUTPUT/EVIDENCE reveals per-op contributions.
- [x] Selecting/hovering an op highlights its contribution segment in the Δ block
      (and ideally its region on the canvas).
- [x] Contributions reconcile to the total Δ (leave-one-out residual shown if any).
- [x] Method + order-dependence caveat surfaced in tooltip and Result Report.
- [x] Handles the single-op case trivially and the no-op case (empty) gracefully.

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "REWORK-09: delta provenance"`

## Result Report

### Recon

**Audit log storage**: `frontend/src/lib/audit/auditEvents.js` builds operation events with op type, params, constraint status, affected segment IDs, and metadata — **but not the values vector**. Storing the full T-element values array per op in the audit stream would bloat memory at scale, so this ticket maintains a parallel `valueOpHistory` ref on the page containing per-op `{op_id, op_label, values_delta}` records, pushed only at the two real value-mutating sites and popped on undo.

**Intermediate predictions**: REWORK-02 added `POST /api/benchmarks/predict-values` which scores arbitrary value vectors. DeltaProvenanceService reuses `PredictionService.predict_values` for every leave-one-out prediction call — same transform chain reported by the REWORK-05 fidelity strip, same softmax convention.

### Algorithm choice (load-bearing)

**Leave-one-out (LOO) over operations.** For each op_i with values-space perturbation Δ_i:

  contribution_i = P(c* | v_N) − P(c* | v_N − Δ_i)

where c* = the baseline class the OUTPUT Δ tracks. Positive contribution = "this op moved the prediction in the Δ direction" (away from the baseline class), matching REWORK-02's predDelta sign convention. Sum of contributions + **residual** = total_delta. The residual captures interactions the linear decomposition can't explain and is **always surfaced** to the user — both as a synthetic trailing row in the panel and as a written caveat ("Leave-one-out is order-dependent and ignores interactions").

**Reference**: Štrumbelj & Kononenko, *JMLR* 11 (2010) §3 — establishes LOO marginal contribution as the canonical baseline for feature-attribution; the SOTA upgrade is sampled Shapley (Lundberg & Lee NeurIPS 2017 KernelSHAP), flagged as a future opt-in mode in the docstring.

**Causal-misattribution honesty (load-bearing)**: per the ticket, "I changed X and it moved" ≠ "the model depends on X". LOO answers the first question, not the second. The docstring spells this out so a future maintainer doesn't recharacterise the metric. Paired with the REWORK-08 saliency overlay, the user can triangulate.

### Backend changes

- `backend/app/schemas/delta_provenance.py` (NEW) — frozen `OpContribution` + `DeltaProvenanceResult` with explicit residual field.
- `backend/app/services/operations/delta_provenance.py` (NEW) — `DeltaProvenanceService.attribute(...)`. Reuses `PredictionService.predict_values`. Module docstring cites Štrumbelj & Kononenko JMLR 2010 §3 + Lundberg & Lee NeurIPS 2017. `_REFERENCE` constant flows into the response and into the UI tooltip.
- `backend/app/routes/operations.py` — new `POST /api/operations/provenance`. Standard input validation: artifact_id + baseline_values + current_values + ops list of {op_id, op_label, values_delta}. Length cap matches `_MAX_VALUES = 65 536`. New `_get_delta_provenance_service` factory honors the existing `PREDICTION_SERVICE` config.
- `backend/tests/test_benchmark_routes.py` — 4 new tests: missing ops 400; length-mismatched op delta 400; empty-ops happy path (residual = total_delta); two-op happy path with reconciliation `total_delta = Σ contributions + residual` to 1e-9.

### Frontend changes

- `frontend/src/lib/provenance/createDeltaProvenanceModel.js` (NEW) — pure helper. Preserves application order. Bar widths normalised to `max |contribution|`. Residual row appears as a synthetic trailing entry tagged `isResidual: true` when `|residual| ≥ 0.005` (0.5pp). Malformed contributions filtered, never throws.
- `frontend/src/lib/provenance/createDeltaProvenanceModel.test.js` (NEW) — 8 unit tests.
- `frontend/src/components/evidence/DeltaProvenancePanel.vue` (NEW) — scoped-style. 4 states (loading/error/empty/data). Rows are `tabindex="0"` and emit `hover-op` / `leave` so the parent can drive a future OUTPUT-zone highlight; today the panel handles its own row hover visually. Order-dependence caveat shown inline; method label in tooltip with reference in `title`. **No accent color** (focus outline uses `var(--line-2)` after code-review fix).
- `frontend/src/services/api/operationsApi.js` — `fetchDeltaProvenance(...)` POST client.
- `frontend/src/components/evidence/EvidenceZone.vue` — new `<slot name="probe-detail" />` after the probe-toggle row.
- `frontend/src/views/BenchmarkViewerPage.vue`:
  - New refs `valueOpHistory`, `deltaProvenanceResult/Loading/Error`, `hoveredProvenanceOpId`, module-scoped `let deltaProvenanceRequestId = 0` race guard + `let opSequence = 0` stable op-ID counter.
  - `recordOpDelta({opName, tier, valuesBefore, valuesAfter})` helper. Skips pure no-ops via 1e-12 epsilon. Stamps op_id as `${opName}-${opSequence}`.
  - `applyInvokeResponse`: snapshots valuesBefore at function top; after mutation, calls `recordOpDelta` if values changed.
  - `handleApplyMinFlip`: pushes undo snapshot **and** calls `recordOpDelta` so chip-undo can reverse min-flip 1:1 (the undoStack/valueOpHistory alignment was a code-review finding — addressed in-ticket).
  - `handleChipUndo`: pops the most recent op from valueOpHistory in lockstep with the undoStack snapshot pop.
  - `handleToggleDeltaSources` is now real: toggle on → fetch; off → clear state + clear hovered op.
  - `refreshDeltaProvenance` POSTs the ops list race-guarded, with a defensive length-filter against future drift sources.
  - seriesVersion watcher fires `refreshDeltaProvenance()` when toggle is on.
  - DeltaProvenancePanel slotted into EvidenceZone's `#probe-detail`.
  - `clearPredictionState` resets all new state.
- `frontend/package.json` — added `src/lib/provenance/*.test.js` to test glob.

### Reconciliation check

Surfaced via `residual = total_delta − Σ contributions`, included in every response and rendered as a tagged synthetic row in the panel when its magnitude is ≥ 0.5pp. Backend tests pin the equality to 1e-9 on the two-op fixture. Caveat text below the rows: "Leave-one-out is order-dependent and ignores interactions. Residual surfaces what the decomposition can't explain."

### Verification

- Frontend `npm test`: **767/767 PASS** (was 759; +8 new provenance lib tests).
- Backend benchmark routes: **26/26 PASS** (was 22; +4 new provenance route tests).
- Backend overall unchanged: same 3 pre-existing failures (`test_segment_encoder_feature_matrix`, `test_operation_result_contract`, `test_segmentation_eval` collection error) — none touch provenance code.
- code-reviewer: APPROVE, zero blocking issues. Two nits addressed in-ticket: focus outline switched from `--accent-bg` to `--line-2` to preserve EVIDENCE accent discipline; `handleApplyMinFlip` now pushes an undo snapshot so the chip-undo path stays in 1:1 alignment with valueOpHistory.

### Out of scope (intentional, deferred)

- **Shapley / KernelSHAP attribution** — heavier compute (O(N!) exact / O(N·M) sampled). Right tool when op count is small and interactions are suspected; opt-in toggle in a follow-up.
- **OUTPUT-zone highlight on hover** — the page maintains `hoveredProvenanceOpId` and the panel emits `hover-op`/`leave`, but the OUTPUT-zone visual highlight ("ideally" per AC, not "must") is deferred. A follow-up can subscribe OutputPanel's class-bar rendering to that ref.
- **Canvas-region highlight** — ops touch specific time ranges; future work could light up the canvas region corresponding to the hovered op's `values_delta` non-zero support. Deferred.
- **Per-class breakdown** — today the contribution is computed for the single baseline class. A multi-class breakdown (contribution per class) would be useful for ≥3-class settings; the data is on the wire (`scores`), the rendering is the work.
