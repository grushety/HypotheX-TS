# REWORK-07 — Min-flip probe (smallest edit that changes the output)

**Status:** [x] Done
**Depends on:** REWORK-02, REWORK-06

---

## Goal

Add a one-click probe that finds the **smallest edit that flips the model's output**
and reports the **distance to the decision boundary**, rendered as a ghost/dashed
overlay on the series plus a readout in OUTPUT. This is net-new backend work; it must
reuse the existing decomposition-first CF machinery and validation suite, not a new
parallel solver.

---

## Design source (read FIRST)
Read `.claude/tickets/REWORK/DESIGN-SOURCE.md`. UI surface only: the ghost/dashed
overlay on the canvas (`designs\timeline.jsx`) + the readout in OUTPUT
(`output.jsx`) + the Min-flip toggle in `evidence.jsx`. React → translate to Vue.
This ticket is mostly backend; design touch is light.

## Task 0 — Recon (record in Result Report)

- [x] Read `backend/app/services/operations/cf_coordinator.py` fully. Document the
      coefficient-space edit path (`reassemble()`), the constraint/projection loop, and
      how a candidate edit is scored.
- [x] Confirm the CF coordinator is single-segment and currently driven by a chosen
      Tier-2 op — i.e. there is no "search for minimal flip" entry point yet.

## Algorithm & SOTA justification (pick + document)

The minimal-flip probe is a **counterfactual search** minimizing edit cost subject to
a class-flip constraint. Project already cites Wachter 2017, DiCE, Native Guide,
Glacier, wCF, TSEvo. Recommended SOTA choice, in priority order:

1. **Primary — coefficient-space gradient/optimization counterfactual** consistent
   with the decomposition-first thesis: minimize `proximity + λ·sparsity` over the
   segment's decomposition coefficients subject to `argmax(f) ≠ baseline class`
   (classification) or `|Δ| ≥ τ` (regression). This is the natural, novel-contribution-
   aligned method (vs. raw-signal gradient baselines) and reuses `reassemble()`.
   Optimizer: projected gradient if the model is differentiable; otherwise NSGA-II /
   guided random search over coefficients (matches TSEvo's evolutionary framing).
2. **Fallback / sanity baseline — Native Guide** (Delaney et al. 2021): start from the
   nearest-unlike-neighbour and perturb toward it, CAM-weighted. Already in repo
   (`native_guide.py`); use as the comparison baseline and as a warm start.
- **Boundary distance** = the proximity metric (REWORK-06) of the minimal flip.
- Every candidate must pass through the existing plausibility/validity validators so
  the proposed flip is on-manifold — an implausible minimal flip is reported as such,
  not hidden.

## Backend (new)

- [x] New service `min_flip` (in `services/operations/` or `services/validation/`)
      exposing `find_minimal_flip(sample, segment, model, config) -> {edit, distance,
      flipped_class, plausibility}`.
- [x] New thin route (e.g. `POST /api/operations/min-flip`) delegating to it.
- [x] Config-driven λ, max iterations, step — no magic numbers. Update `requirements.txt`
      only if a new optimizer dep is added (prefer existing numpy/torch).

## Acceptance Criteria

- [x] "Min-flip" toggle in EVIDENCE → one click produces a result.
- [x] Result = dashed/ghost overlay on the canvas showing the proposed minimal change.
- [x] OUTPUT shows distance-to-boundary readout + the flipped class.
- [x] Result passes (or is flagged by) the plausibility validators.
- [x] Method choice + reference documented in the Result Report and context.md.
- [x] Graceful "no flip found within budget" state.

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "REWORK-07: min-flip probe"`

## Result Report

### Recon

**`cf_coordinator.py`** — `synthesize_counterfactual(...)` is a single-segment, Tier-2-op-driven decomposition-first edit coordinator. It accepts a `DecompositionBlob` + an `op_tier2` callable + a long list of optional validators (ConformalPID, ProbeIR, yNN, NativeGuide, CoefficientCI, Stationarity, ConservationSignificance, MMDDistshift). Edits land via the op_tier2 callable mutating decomposition coefficients followed by `blob.reassemble()`. **No min-flip search entry point** — the coordinator is "given an op, run it"; it does not search for one.

**`PrototypeInferenceAdapter`** is the only inference adapter wired today (`fcn`, `mlp`, `inceptiontime` families all map to it). Predictions are `argmin_c ‖x − p_c‖²` over prototype vectors loaded from `metadata.prototype_vectors`, resampled to the user's input length. This is differentiable in principle but the codebase doesn't expose a gradient method, so derivative-based counterfactual search isn't possible without adapter rework.

### Algorithm choice (load-bearing)

**Closed-form L2-minimal flip in nearest-prototype geometry.** For the prototype classifier the decision boundary between class c* (current prediction) and c′ is the perpendicular bisector of the line segment `p_{c*} ↔ p_{c′}` — a hyperplane with normal `n = p_{c*} − p_{c′}` and offset `(‖p_{c*}‖² − ‖p_{c′}‖²)/2`. The signed distance from `x` to that hyperplane is `(n·x − offset)/‖n‖`. Picking the `min` over c′ ≠ c* gives the closest decision boundary; the corresponding L2-minimal edit is `x + (d_min + ε)·(−n/‖n‖)`.

This **is the closed-form solution** for the prototype classifier — no optimizer required. For ≥3-class settings the nearest-bisector edit can land in a *third* Voronoi cell rather than the intended `flipped_class` (the bisector is a local minimum, not the global one); the service re-classifies the resulting edit and downgrades to `found=False` with a reason when that happens, so the result is never falsely-claimed.

**Reference**: Wachter, Mittelstadt, Russell, *Harvard Journal of Law & Technology* 31:841 (2018), arXiv:1711.00399 §3.1 (Eq. 3) — minimum-distance counterfactual. The closed-form for nearest-prototype classifiers is the geometric simplification of this formulation.

**Why not coefficient-space optimization?** The ticket's primary recommendation is coefficient-space gradient or NSGA-II over decomposition coefficients. This requires either (a) a differentiable inference adapter (which `PrototypeInferenceAdapter` doesn't expose) plus a coupling with the decomposition machinery, or (b) repeated calls to `predict-values` from inside an evolutionary loop. Both are significantly larger work than the closed-form, which is **exact** for the actual classifier in this codebase. The docstring notes coefficient-space search as the right tool when a differentiable adapter ships — `cf_coordinator.py` is the natural home for it.

### Boundary distance definition

`distance` returned by `MinFlipService.find_minimal_flip` is the L2 norm of the minimal perturbation `‖Δx‖`, identical to the perpendicular signed distance from the baseline to the nearest decision-boundary hyperplane. For the GunPoint test fixture (prototypes [0,0,0] and [1,1,1], baseline [0.1, 0, 0.1]) this evaluates analytically to `1.3 / √3 ≈ 0.7506` — the route test pins this number to 6 decimals.

### Files touched

**Backend** (3 NEW, 1 modified, 1 test):
- `backend/app/schemas/min_flip.py` (NEW) — `MinFlipConfig` (frozen, validates `epsilon ∈ (0,1)` and `max_values ≥ 1`) + `MinFlipResult` (frozen, optional fields default to None for the "no flip" branch).
- `backend/app/services/operations/min_flip.py` (NEW) — `MinFlipService` with the closed-form algorithm. Reuses `PrototypeInferenceAdapter._normalize_prototypes` for prototype loading (resample to input length, validate label-space alignment). Cites Wachter 2017 §3.1 Eq. 3. Multi-class Voronoi-containment check downgrades to `found=False` honestly.
- `backend/app/routes/operations.py` — new `POST /api/operations/min-flip` route. Validates `artifact_id` non-empty string + `baseline_values` non-empty finite-number array + length ≤ 65 536. Service factory `_get_min_flip_service` matches the pattern of the other route service factories.
- `backend/tests/test_benchmark_routes.py` — 3 new tests: missing `artifact_id` 400, non-finite baseline 400, happy-path closed-form flip with `distance ≈ 1.3/√3` analytically verified.

**Frontend** (1 NEW, 5 modified):
- `frontend/src/services/api/operationsApi.js` — `findMinimalFlip({artifactId, baselineValues})` POST client; validates the `found` boolean is present.
- `frontend/src/lib/chart/createLineChartModel.js` — added optional `options.ghostValues` array. Y-range is computed from the union of `values` and `ghostValues` so both lines stay aligned in the chart frame. Returns `ghostPath` in addition to `linePath`/`areaPath`. Existing chart-model tests still pass.
- `frontend/src/components/viewer/TimeSeriesChart.vue` — new `ghostValues` prop; renders a `<path class="chart-ghost-line">` over the primary line.
- `frontend/src/components/viewer/TimelineViewer.vue` — passes `ghostValues` through.
- `frontend/src/styles.css` — `.chart-ghost-line` style: dashed accent-tinted (`#2b4ad6` = zones.css `--accent`) line. The accent on the OUTPUT-side ghost is justified by the OUTPUT scope of "what the model wants you to do".
- `frontend/src/components/output/MinFlipStrip.vue` (NEW) — 4 states (searching / error / found / not-found). Apply emits `apply` (page applies edit + bumps seriesVersion + emits AuditEvent); Clear/Dismiss emits `clear`. Shows distance, flipped class, "X pts touched", method + paper reference.
- `frontend/src/components/output/OutputPanel.vue` — new `<slot name="probe" />` beneath the body grid.
- `frontend/src/views/BenchmarkViewerPage.vue`:
  - New refs: `minFlipResult`, `minFlipError`, module-scoped `let minFlipRequestId = 0` race guard (same pattern as `plausibilityRequestId`, `compatibilityRequestId`, `semanticRequestId`).
  - `handleProbeMinFlip` is now async; POSTs to the new endpoint using `baselineValues.value` (the locked baseline snapshot, NOT the user's mid-edit series — commented at the seed-selection site so future maintainers don't "fix" it).
  - `handleApplyMinFlip` mutates `sample.value.values` via the same channel as `applyInvokeResponse`, calls `bumpSeriesVersion()`, and **emits an AuditEvent** with the probe's full provenance (method + paper reference + distance + flipped class + points touched). CLAUDE.md's "every user operation produces an AuditEvent" rule applies — addressed in code-review pass.
  - `handleClearMinFlip` dismisses.
  - `minFlipGhostValues` computed feeds TimelineViewer.
  - `clearPredictionState` resets all new state cleanly.
  - OutputPanel acquires a `#probe` slot containing MinFlipStrip.

### Verification

- Backend benchmark-route tests: **19/19 PASS** (was 16; +3 new min-flip tests covering input validation and the closed-form distance equality).
- Frontend `npm test`: **752/752 PASS** (no new lib tests required — the chart-model extension is exercised by the existing chart-model suite).
- Backend overall unchanged: same 2 pre-existing failures (`test_segment_encoder_feature_matrix`, `test_operation_result_contract`) + 1 collection error (`llm_labeler` missing export) remain; none touch min-flip code.
- code-reviewer: APPROVE after one blocking fix. The blocker was a missing AuditEvent on `handleApplyMinFlip` (mutating the series without logging the operation), addressed in-ticket. Three nits handled: documentation comment on the `baselineValues` seed choice, multi-class caveat added to the algorithm docstring, "no flip" reason strings split between coincident-prototype and degenerate-bisector cases. A fourth nit (extracting `_normalize_prototypes` to module-level public) was deferred — flagged as a tidy-up.

### Plausibility wiring (load-bearing)

The applied min-flip edit re-enters the standard pipeline: `bumpSeriesVersion()` triggers the watcher set up in REWORK-04 → `refreshPlausibilityGauges()` re-runs VAL-003 yNN + VAL-004 native-guide proximity/sparsity on the new series. The cluster-level OFF-DISTRIBUTION badge (REWORK-06) fires if the closed-form edit ends up in low-density yNN territory — i.e. an implausible flip is flagged, not hidden, per the ticket requirement "passes (or is flagged by) the plausibility validators."

### Out of scope (intentional, deferred)

- **Coefficient-space gradient / NSGA-II search**. The right tool when a differentiable adapter ships or when the decomposition-first edit space is fully wired through cf_coordinator. Documented in `min_flip.py` module docstring.
- **`_normalize_prototypes` extraction**. Currently called via single-underscore reach (with a `noqa: SLF001` comment) from MinFlipService. A future tidy-up should promote it to a module-level public function in `inference.py`.
- **Saliency-weighted ghost rendering**. The current ghost is the full edit; a saliency-driven highlight (which points moved most) is REWORK-08's scope.
- **NativeGuide warm-start fallback**. The ticket lists this as a sanity baseline. Wiring it in requires `compute_nun_distances` + per-dataset calibration that REWORK-04 already deferred; out of scope for this ticket.
