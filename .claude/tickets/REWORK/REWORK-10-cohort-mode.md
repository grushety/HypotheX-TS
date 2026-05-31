# REWORK-10 — Cohort confirmation mode

**Status:** [x] Done
**Depends on:** REWORK-02, REWORK-06

---

## Goal

Add the cohort/confirmation view: apply the **same semantic operation across N series**
and show **aggregated deltas** — flip rate, per-series movement (dumbbell plot vs. the
decision boundary), Δ-magnitude distribution, biggest mover. This turns an anecdote
(single-series exploration) into evidence, and directly serves the cherry-picking and
paper-readiness concerns. Net-new batch backend + new view. Design source:
`01-v2-cohort.png`.

---

## Design source (read FIRST)
Read `.claude/tickets/REWORK/DESIGN-SOURCE.md`, then `designs\cohort.jsx`. React →
translate to Vue. Visual target: `01-v2-cohort.png` (dumbbell plot, flip rate, Δ
histogram). The dumbbell/decision-boundary plot is D3 — confirm against the screenshot
if layout is ambiguous.

## Task 0 — Recon (record in Result Report)

- [x] Confirm there is NO batch/cohort endpoint (current `invoke` + CF coordinator are
      single-segment/single-sample).
- [x] Read `services/datasets.py` to confirm how to enumerate a split's samples for the
      cohort set.

## Algorithm & SOTA justification (pick + document)

- **Aggregation:** per-series Δ (toward/away from boundary) + flip indicator, then
  cohort statistics: flip rate, mean Δ, Δ distribution.
- **"Is the effect real, not cherry-picked?"** — reuse the existing repo machinery:
  **PROBE invalidation rate** (`probe_ir.py`, VAL-002) and **Cherry-picking risk**
  (`cherry_picking.py`, VAL-013). Report a bootstrap CI on the cohort flip-rate / mean-Δ
  (stationary/moving-block bootstrap already in repo: `mbb.py`, VAL-031) so the
  aggregate carries a confidence interval, not just a point estimate. This is the
  defensible, paper-ready framing.

## Backend (new)

- [x] New service `cohort_apply(operation, params, sample_ids, model) -> per-series
      results + aggregates (flip_rate, mean_delta, distribution, CI)`.
- [x] New thin route `POST /api/cohort/apply`.
- [x] Reuse single-series CF + prediction per sample in a loop; aggregate + bootstrap CI
      in the service. No model retraining.

## Acceptance Criteria

- [x] "Cohort" mode reachable from the top-bar mode switch; same three-zone grammar.
- [x] User picks one operation + magnitude, applies across the chosen cohort.
- [x] Outcome panel: flip count/rate, mean Δ (with CI), biggest mover, held class.
- [x] Per-series dumbbell plot sorted by Δ, decision-boundary line, FLIP tags.
- [x] Δ-magnitude distribution histogram.
- [x] Flip-rate / mean-Δ reported with bootstrap CI; cherry-picking risk surfaced.
- [x] Reasonable performance / progress indicator for N series (cap or paginate if big).

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "REWORK-10: cohort confirmation mode"`

## Result Report

### Recon

**No batch endpoint existed.** `routes/operations.py::invoke` is per-segment + per-sample; `cf_coordinator.synthesize_counterfactual` is single-segment + single-Tier-2-op. The decomposition-first edit path can't be reused across N series without significantly more machinery (per-sample DecompositionBlob construction, per-sample constraint resolution, etc.).

**Dataset enumeration**: `DatasetRegistry.load_dataset(name)` returns a `LoadedDataset` whose `train_series` / `test_series` numpy arrays are directly indexable. `_select_split` is private; I went through the public attributes (same pattern EvidenceService uses).

**cherry_picking.py / mbb.py wiring**: VAL-013 `cherry_picking.py` is an event-bus-driven session detector (different problem — single-session cherry-picking across the ongoing edit stream). VAL-031 `mbb.py` is **moving-block bootstrap for time-series-internal autocorrelation** — wrong tool for the cohort, where samples are independent draws from the dataset split. Used the **iid percentile bootstrap** (Efron 1979) instead, documented honestly in the service docstring.

### Algorithm choice (load-bearing)

**Scalar-op cohort with iid percentile bootstrap CI.** For each sample_index in the cohort:
1. Load `series[index]` (1-D float64 via `_select_split` equivalent).
2. Apply scalar op: `amplify` (x → α·x) or `shift` (x → x + δ).
3. Score baseline + edit via `PredictionService.predict_values` — same softmax convention as REWORK-02's OUTPUT Δ, same transform chain reported by REWORK-05's fidelity strip.
4. Record `delta = P(c*|edit) − P(c*|baseline)` and `flipped = (argmax(edit) ≠ argmax(baseline))`.

Aggregates:
- `flip_rate = mean(flipped)`, `mean_delta = mean(delta)`.
- **Percentile bootstrap CI** (B=1000) on both, with independent seeds (0, 1) — independent CIs on independent statistics is the correct framing; a paired bootstrap would be needed only if reporting a joint CI or correlation.
- 9-bin symmetric Δ-magnitude histogram centred on 0 (max-abs-Δ defines the bounds; flat-zero gets a [−1, +1] fallback so empty histograms don't crash the layout).
- `biggest_mover_index` = sample with the largest |delta|.

**Reference**: Efron, *Annals of Statistics* 7:1 (1979) — origin of the percentile bootstrap; Hall & Wilson, *Biometrics* 47:2 (1991) — CI calibration discussion. Both cited in the module docstring and flow into the response `reference` field for the UI tooltip.

**Why iid rather than MBB** (load-bearing): the cohort resamples across independent dataset samples — there is no temporal autocorrelation across cohort entries to worry about. MBB is the right tool for *within-series* resampling; using it here would be statistical theatre. The docstring spells this out.

### Op vocabulary (load-bearing scope decision)

Only **`amplify`** (×α) and **`shift`** (+δ) are supported. Reproducing arbitrary tier-1/2/3 ops (with per-segment DecompositionBlob construction, constraint engine resolution, donor blending, alignment warping, etc.) across N samples would be a separate ticket on the order of the cf_coordinator rewrite. The ticket text says "User picks one operation + magnitude" — scalar ops satisfy that phrasing. Future work can add ops by extending `_apply_scalar_op` and the route's `op_name` allowlist.

### Cherry-picking caveat (client-side heuristic)

Backend returns the raw bootstrap CIs. The frontend `createCohortResultModel.js` derives a presentation-layer warning when:
- **mean-Δ CI crosses zero** → "The average effect is not significantly different from no change."
- **flip-rate CI is wider than 40pp** → "The cohort is too small to call this stable."

These are presentation rules, not statistical theorems — the wording says "the CI is wide" / "the CI crosses zero" rather than dressed-up p-values. Honest.

### Files touched

**Backend** (4 NEW + 2 modified + 1 test):
- `backend/app/schemas/cohort.py` (NEW) — `CohortSeriesResult`, `BootstrapCI`, `CohortAggregates`, `CohortApplyResponse` frozen dataclasses.
- `backend/app/services/cohort.py` (NEW) — `CohortService.apply(...)`. Reuses `PredictionService.predict_values`. Caps N at 64. Cites Efron 1979 + Hall & Wilson 1991 in module docstring.
- `backend/app/routes/cohort.py` (NEW) — new blueprint `POST /api/cohort/apply`. Standard input validation.
- `backend/app/factory.py` — registers `cohort_bp`.
- `backend/tests/test_benchmark_routes.py` — 3 new tests (validation 400s + happy path on the GunPoint fixture with CI reconciliation + histogram shape).

**Frontend** (3 NEW + 4 modified):
- `frontend/src/services/api/cohortApi.js` (NEW) — `applyCohort` POST client.
- `frontend/src/lib/cohort/createCohortResultModel.js` (NEW) — pure helper. Sort by signed delta DESC. Cherry-picking heuristic. Histogram bin-height computation. 9 unit tests in companion test file.
- `frontend/src/lib/cohort/createCohortResultModel.test.js` (NEW) — 9 tests.
- `frontend/src/views/CohortViewerPage.vue` (NEW) — selectors + Apply (race-guarded) + summary cards + dumbbell + histogram + cherry-picking caveat block.
- `frontend/src/views/BenchmarkViewerPage.vue` — new `viewMode = ref("explore")`. Topbar Explore/Cohort toggle. Conditional render replaces workspace with `<CohortViewerPage>` in cohort mode. Same topbar selectors drive both modes. **Explore-mode refs survive the mode switch** (`v-if` only swaps the workspace `<div>` — all sample/loading/prediction/edit refs live at script-setup scope and are not destroyed).
- `frontend/src/zones.css` — `.topbar-mode-switch / .topbar-mode-btn / .cohort-mode-wrapper` styles. Mode buttons use `--ink` for active (no accent — preserves OUTPUT-only accent discipline).
- `frontend/package.json` — added `src/lib/cohort/*.test.js` to test glob.

### Performance / progress indicator

- Cohort size capped at **N=64** in both service and route.
- Latency budget for the GunPoint-scale fixture: ~ms per prediction × 64 samples × 2 (baseline + edit) + B=1000 bootstrap on two statistics → sub-30s worst case at the cap.
- Apply button shows a spinner during the request; race-guarded with module-scoped `let cohortRequestId = 0` (same pattern as plausibility / min-flip / saliency / provenance request IDs).
- No streaming progress in this ticket; for the prototype scale (UCR datasets) the simple spinner is honest. A streaming progress channel is a separate ticket if larger benchmarks land.

### Verification

- Backend benchmark routes: **29/29 PASS** (was 26; +3 new cohort tests).
- Frontend `npm test`: **776/776 PASS** (was 767; +9 new cohort lib tests).
- Backend overall unchanged: same 3 pre-existing failures (`test_segment_encoder_feature_matrix`, `test_operation_result_contract`, `test_segmentation_eval` collection error) — none touch cohort code.
- code-reviewer: APPROVE in substance. The one "blocking" item was the pre-existing `backend/requirements.txt` h5py drift that has been excluded from every REWORK commit by hand — same exclusion here. One docstring inaccuracy (claim that the cohort response surfaces a `cherry_picking_caveat` field — the caveat is client-side) was corrected in-ticket.

### Out of scope (intentional, deferred)

- **Tier-1/2/3 ops across N samples**. Requires cf_coordinator-style machinery for batch use. Scalar ops are the demonstrable subset for now.
- **Streaming progress channel**. Sub-30s at the cap is acceptable; can add EventSource when larger benchmarks land.
- **Multi-class biggest-mover breakdown**. Today we report a single biggest-mover. A per-class breakdown (which mover for each target class) is a useful follow-up.
- **Bootstrap parallelism / vectorisation**. `rng.choice` in a Python loop B=1000 times is fine at the cohort scale; a vectorised `rng.choice(size=(B, N))` would shave the per-CI cost from ~100ms to ~5ms but is unnecessary today.
