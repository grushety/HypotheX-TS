# REWORK-02 — Output panel: Baseline / Current / Δ

**Status:** [x] Done
**Depends on:** REWORK-01

---

## Goal

Build the OUTPUT zone — the missing center of the what-if tool. Show the model's
prediction on the **Baseline** (locked, original series) vs. **Current** (edited
series), with **Δ** as the full-width hero, including an unmissable class-flip flag.
Backend prediction already exists; this ticket assembles and correctly wires it.

---

## Design source (read FIRST)
Read `.claude/tickets/REWORK/DESIGN-SOURCE.md`, then `designs\output.jsx` (React —
translate to Vue, do not port verbatim). Visual target: `Output Panel - Variants.html`
and `out-normal.png` / `out-empty.png` / `out-stale.png`. Ask the user to confirm if
state layouts are ambiguous.

## Task 0 — Recon (record in Result Report)

- [x] Confirm `services/api/benchmarkApi.fetchBenchmarkPrediction` returns the
      normalized schema needed (task type, classes, probabilities, predicted_index,
      regression value). Read `backend/app/services/inference.py` +
      `backend/app/schemas/prediction.py` and document the exact response shape.
- [x] Confirm `comparison/ModelComparisonPanel.vue` can be reused or must be
      replaced; note the gap.
- [x] Identify the existing edit/apply hook in `BenchmarkViewerPage.vue` that fires
      after an operation (this drives Current recompute + stale state).

## Backend verification (must hold before frontend is "done")

- [x] `PredictionService` returns, for the active sample, calibrated class
      probabilities (classification) or scalar/forecast (regression) via the
      declared inference adapter. If the normalized fields the UI needs are not all
      present, add them in the service/schema **in this ticket** (thin route stays
      thin).

## Acceptance Criteria

- [x] Baseline prediction computed once on sample load and **locked** as reference.
- [x] Current prediction recomputes after each applied operation.
- [x] Δ block spans full width of the OUTPUT column (hero), shows per-class
      probability shift (classification) or signed numeric delta (regression).
- [x] **Class flip** (argmax change) is visually unmistakable (color + icon + text).
- [x] Four states implemented and reachable: **empty** (no sample), **loading**,
      **stale** (edited since last run → re-run affordance, never show old numbers as
      current), **error** (with retry).
- [x] Classification and regression render modes both handled (whichever the active
      benchmark needs verified live; the other at least correct from schema).

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "REWORK-02: output panel baseline/current/delta"`

## Result Report

### Recon

**Backend prediction shape (pre-rework, `PredictionResponse`):**
- `dataset_name`, `artifact_id`, `split`, `sample_index` — request echo
- `predicted_label: str` — argmax label
- `true_label: str | None` — ground-truth label
- `scores: tuple[PredictionScore(label, score, probability), ...]`

The dataset registry is classification-only today; no regression adapter exists.

**Gaps the UI needs vs. what existed:**
1. **Task discriminator**: not in the response. Added `task: str = "classification"` to PredictionResponse + included in new ad-hoc response. Regression mode is wired through the state machine for the day a regression adapter ships.
2. **Predicted index**: derivable client-side via `scores.findIndex(s => s.label === predicted_label)`; the state helper does this. No backend change.
3. **Endpoint to predict on edited values**: did not exist. Added `POST /api/benchmarks/predict-values` returning the new `AdHocPredictionResponse` (artifact_id + predicted_label + scores + task). Skips dataset loading and compatibility validation — the caller (the workbench) has produced the values themselves.

**ModelComparisonPanel reuse vs rebuild:** REBUILT. MCP is the segmentation labeler suggestion UI (LLM / prototype proposals → accept / override / adapt-model). It does not show predictions at all. Built a fresh `OutputPanel` and moved MCP to the INPUT z1-rail where it belongs (matches the design's `app.jsx` placement of `ModelComparison` in z1-rail).

**Operation/edit hook for Current recompute:** the funnel is `applyInvokeResponse` in `BenchmarkViewerPage.vue` — every backend operation lands here and may rewrite `sample.value.values` (either via `response.values` for a single-segment op or via `response.extra.aligned_segments` for align/warp). The second mutation site is `handleChipUndo`, which restores `values` from an undo snapshot. Bumping a monotonic `seriesVersion` at these two sites is sufficient to drive the stale signal; the remaining mutation paths (boundary moves, label edits, scope edits, chip accept/override) touch segments only, not values, so they don't invalidate the prediction.

### Design translation

`designs/output.jsx` (React) was re-implemented as `frontend/src/components/output/OutputPanel.vue` (Vue 3, scoped CSS). Class names preserved (`out-grid`, `out-block`, `cls-row`, `flip`, `dvg-row`, etc.) so the design's visual language carries over. Uncertainty rendering (entropy / near-tie bar) is **not** in this ticket — it is REWORK-03's scope.

### Files touched

- `backend/app/schemas/prediction.py` — added `task` field to `PredictionResponse`; new `AdHocPredictionResponse` frozen dataclass.
- `backend/app/services/inference.py` — refactored shared scoring into `_resolve_adapter` + `_score`; added `PredictionService.predict_values(artifact_id, values)`.
- `backend/app/routes/benchmarks.py` — new `POST /api/benchmarks/predict-values` with input validation: non-empty list, every element a finite number, length ≤ 65 536 (DoS cap). Existing `/prediction` GET response now also includes `task`. New `_serialize_scores` helper consolidates score serialization.
- `frontend/src/services/api/benchmarkApi.js` — new `predictBenchmarkValues(artifactId, values)` POST client.
- `frontend/src/lib/output/createOutputPanelState.js` — new pure state machine. Precedence: error > loading > empty > stale > normal. Aligns baseline + current probabilities by label (preserves baseline order regardless of how current ranks classes), computes class-flip flag and `predDelta` (signed shift of baseline class confidence), clamps probabilities to [0, 1].
- `frontend/src/lib/output/createOutputPanelState.test.js` — 11 unit tests covering all five states, flip detection, delta sign, label alignment, probability clamping, and regression mode.
- `frontend/src/components/output/OutputPanel.vue` — new component. Renders all five states. Δ block uses `grid-column: 1 / -1` to span the two-column out-grid (full-width hero). Class flip uses accent-tinted card + icon + crossed-out old class. Stale state veils the body and overlays a "Re-run prediction" card.
- `frontend/src/views/BenchmarkViewerPage.vue` — added refs `baselinePrediction`, `currentPrediction`, `seriesVersion`, `currentPredictionVersion`; helper `bumpSeriesVersion()`; handler `handleRerunPrediction` (falls back to `handleRequestPrediction` when no baseline yet); computed `outputPanelState` + `outputPanelArtifactLabel`. Bump version inside `applyInvokeResponse` (only when a values mutation actually fires) and inside `handleChipUndo`. Moved `<ModelComparisonPanel>` to the INPUT z1-rail. Mounted `<OutputPanel>` in the OUTPUT zone.

### Verification

- Frontend: 702/702 PASS (49 suites; includes the 11 new output-panel tests).
- Backend route tests: 11/11 PASS on `test_benchmark_routes.py` after backend nit fixes (DoS cap + finite-number check).
- Backend overall: 2548 PASS / 1 FAIL (stale embedding-size assertion, pre-existing) / 1 collection error (unrelated `llm_labeler` import). The "missing operation-result fixture" pre-existing failure no longer reproduces — that test is now green on this branch.
- code-reviewer: APPROVE, zero blocking issues. Two backend nits (DoS cap, non-finite numbers) addressed inside this ticket. Two optional polish items (race-id guard on `handleRerunPrediction`, audit event on re-run) deferred: the race is UX-only (worst case the freshness chip blips STALE briefly) and re-run doesn't change the series, so the underlying edits' audit events already cover the timeline.

### Out-of-scope (intentional)

- Uncertainty bar / entropy display inside Current block → REWORK-03.
- Regression backend adapter → no ticket yet; client-side state machine handles `task: "regression"` if it ever ships.
- Δ provenance (sources / attribution of the change) → REWORK-09.
- Pin-to-shoebox affordance on the panel head → REWORK-11.
