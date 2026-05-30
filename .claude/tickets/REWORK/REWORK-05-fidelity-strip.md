# REWORK-05 — Fidelity "Model sees this" strip

**Status:** [x] Done
**Depends on:** REWORK-02, REWORK-04

---

## Goal

Add the trust feature: a compact "Model sees this" strip showing the **exact
preprocessed series** fed to the model (after normalization / resampling / windowing),
so the scientist can verify the edited series reaches the model as intended. Expandable
to a preview comparing raw-edited vs. model-input series. This guards against the
single most insidious what-if failure: silent preprocessing mismatch.

---

## Design source (read FIRST)
Read `.claude/tickets/REWORK/DESIGN-SOURCE.md`, then `designs\evidence.jsx` (the
"Model sees this" strip). React → translate to Vue. Visual target: `01-z-sbxmodal.png`.

## Task 0 — Recon (record in Result Report)

- [x] Read `backend/app/services/inference.py` (`_vectorize_sample`,
      `_resample_vector`, prototype normalization) and trace the FULL transform chain
      applied between user-edited series and model input.
- [x] Determine whether the post-transform array is currently exposed by any endpoint.
      Document: exposed / not exposed.

## Backend verification (likely sub-task here)

- [x] If the preprocessed input is NOT already returned, add a field to the prediction
      response (or a thin `GET`/flag) that returns the exact array the model consumed,
      plus the ordered list of transforms applied (name + params). Logic in
      inference service; route stays thin.
- [x] The strip must reflect the REAL transform chain — not a re-implementation in JS.
      Single source of truth = the backend transform path.

## Acceptance Criteria

- [x] Collapsed: a one-line "Model sees this · N transforms · ✓ compatible" strip.
- [x] Expanded: overlay/preview of raw-edited series vs. exact model-input series, and
      the named transform list.
- [x] If a compatibility/shape mismatch exists, the strip warns clearly (ties into the
      existing `CompatibilityValidator`).
- [x] Values come from backend, verified identical to what `PredictionService` uses.

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "REWORK-05: fidelity model-sees-this strip"`

## Result Report

### Recon — transform chain

Traced the full path from user-edited series to the prototype-distance score:

**Dataset path (`GET /api/benchmarks/prediction`)**:
1. `DatasetRegistry.load_dataset` → `LoadedDataset.train_series` / `test_series` are 3-D `(n_samples, n_channels, series_length)` numpy arrays, dtype typically float32.
2. `_select_sample` returns `series[sample_index]` → 2-D `(n_channels, series_length)`.
3. `PrototypeInferenceAdapter._vectorize_sample` → `np.asarray(sample, dtype=np.float64).reshape(-1)` → 1-D float64.
4. Adapter scores against prototypes; prototypes themselves are RESAMPLED to match the user input length (`_resample_vector`), but the user's array is unchanged after step 3.

**Ad-hoc path (`POST /api/benchmarks/predict-values`)**:
1. Frontend sends `values: [number, number, ...]` — JSON floats.
2. Route validates finite numbers + length cap. Calls `PredictionService.predict_values`.
3. The service originally re-ran the same cast+flatten via `_vectorize_sample` (idempotent on 1-D float64 input).

**Pre-rework exposure**: NONE. Neither endpoint returned the transform list nor the model-input length. The fidelity strip would have had nothing real to surface.

### Backend changes — single source of truth

The cast+flatten work is now centralised in `PredictionService._transform_input(sample) -> (np.ndarray, tuple[PredictionTransform, ...])`. It applies the two deterministic input-side transforms and returns both the transformed array and ordered descriptors. The adapter's own `_vectorize_sample` becomes idempotent on the result, so the descriptor list IS the full input-side preprocessing path. **Prototype-side resampling stays in the adapter** — it adapts each prototype to the user's input length but does not modify the user's array, so it doesn't belong in the "Model sees this" strip. The docstring spells this out explicitly to defuse the future "what about prototype resampling?" question.

Both `PredictionResponse` and `AdHocPredictionResponse` carry:
- `transforms: tuple[PredictionTransform, ...]` — each entry has `name`, `params: dict`, `before_shape: tuple[int]`, `after_shape: tuple[int]`. Defaults to empty tuple for backwards-compat.
- `model_input_length: int | None` — the length of the 1-D float64 array the adapter actually scored.

The new fields are serialised by `_serialize_transforms` in the benchmarks route. Two new route tests pin the behaviour: dataset-path samples produce `[cast_float64, flatten]` with the correct float32→float64 + (1, T)→(T,) descriptors; 1-D float predict-values input produces an empty transform list and the correct length.

### Frontend changes — formats, never re-implements

`createFidelityStripState` is a pure helper. It does NOT re-derive any transform — it only formats the backend's descriptors into UI rows. JSDoc says so explicitly. Returns:
- `status: "ok" | "warn" | "empty"` — drives the collapsed-strip tone and disables the head when empty.
- `headline: string` — collapsed one-liner. Either `"Model sees this · run a prediction to see the transform chain"` (empty), `"Model sees this · N transforms · ⚠ M issues"` (warn — ties to `CompatibilityValidator` messages), or `"Model sees this · {identity (0 transforms) | N transforms} · ✓ compatible · L values"` (ok).
- `transforms: [{name, label, caption, beforeShape, afterShape}, ...]` — UI rows with human labels (`"Cast to float64"`, `"Flatten to 1-D"`) and shape-transition captions.
- `compatibility: { ok: boolean, messages: string[] }` — passed through verbatim from `CompatibilityValidator`.

`FidelityStrip.vue` mounts via EvidenceZone's `fidelity` slot. Collapsed head shows the one-liner with a FRESH / WARN / "—" tone tag. Expanded body shows the numbered transform list, an "identity" callout when 0 transforms ship (says "no dtype cast, no flatten, no windowing"), a compatibility-warnings block with `role="alert"`, and an SVG overlay of edited (dashed grey) vs model-input (solid ink) series. When the two are identical (typical for univariate float64 input) the model line is suppressed and an "identical to edit" tag appears in the legend. No `--accent` references; EVIDENCE colour discipline preserved.

### Files touched

**Backend** (4 files):
- `backend/app/schemas/prediction.py` — `PredictionTransform` frozen dataclass; `transforms` + `model_input_length` on both response shapes.
- `backend/app/services/inference.py` — new `_transform_input` static helper; both `predict()` and `predict_values()` use it. Adapter call now takes the already-transformed array.
- `backend/app/routes/benchmarks.py` — `_serialize_transforms` helper; both prediction endpoints emit the new fields.
- `backend/tests/test_benchmark_routes.py` — 2 new tests (16 total).

**Frontend** (5 files):
- `frontend/src/lib/fidelity/createFidelityStripState.js` (NEW) — pure helper.
- `frontend/src/lib/fidelity/createFidelityStripState.test.js` (NEW) — 7 tests.
- `frontend/src/components/evidence/FidelityStrip.vue` (NEW) — component.
- `frontend/src/views/BenchmarkViewerPage.vue` — imports, `fidelityStripState` computed, slot wiring.
- `frontend/package.json` — added `src/lib/fidelity/*.test.js` to test glob.

### Verification

- Frontend `npm test`: 747/747 PASS (was 740; +7 new fidelity tests).
- Backend `test_benchmark_routes.py`: 16/16 PASS (was 14; +2 new transform tests).
- Backend overall unchanged: the 2 pre-existing failures (`test_segment_encoder_feature_matrix.py`, `test_segmentation_eval.py` collection error) are unrelated to REWORK-05.
- code-reviewer: APPROVE after fixes. One blocking issue (`backend/requirements.txt` h5py drift) was a pre-existing untracked modification that has been excluded from every REWORK commit — same exclusion here. Two nits handled in-ticket: docstring clarified that prototype-side resampling is intentionally not in `_transform_input`; head caret hidden when status is empty.

### Out of scope (intentional)

- **Windowing / normalization transforms** — none exist in the codebase today; the prototype adapter directly consumes the cast+flatten output. If a future ticket adds e.g. z-score normalization or sliding-window slicing, the new step lands as another `PredictionTransform` entry and the strip surfaces it automatically with no UI change.
- **Multivariate channel handling** — current benchmarks are univariate. For `n_channels > 1` the flatten step concatenates channels in C-order; the descriptor already records the `before_shape=(n_channels, T)` → `after_shape=(n_channels * T,)` transition, so the strip will display the correct caption when multivariate datasets land.
- **CompatibilityValidator length mismatch via predict-values** — `predict-values` carries no dataset context, so length-mismatch warnings only fire on the GET prediction path. This is fine: the user picked an artifact, the model adapted via prototype resampling, no constraint violated.
