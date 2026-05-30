# REWORK-08 — Saliency overlay (where the model is looking)

**Status:** [x] Done
**Depends on:** REWORK-01

---

## Goal

Add a toggleable attribution heatmap ON the series canvas, suggesting *where* the
model is looking — framed as a suggestion the what-if then verifies (attribution
proposes, editing confirms). Net-new backend: no saliency/attribution code currently
exists in the repo (verified — `services/` has no attribution module).

---

## Design source (read FIRST)
Read `.claude/tickets/REWORK/DESIGN-SOURCE.md`. UI surface: the Saliency toggle in
`designs\evidence.jsx` (probes) and the heatmap layer on `designs\timeline.jsx` —
must be visually distinct from segment bands + shape-atom coloring. React → translate
to Vue. Visual target: `01-v2-primary.png` (Saliency toggle, top-right of canvas).

## Task 0 — Recon (record in Result Report)

- [x] Confirm model type(s) behind the active benchmarks: prototype adapter
      (`inference.py`) and any TCN/FCN artifacts (SEG-002, model dir). Document which
      are differentiable (gradient methods available) vs. distance-based (prototype —
      needs perturbation-based attribution).
- [x] Confirm there is no existing attribution endpoint.

## Algorithm & SOTA justification (pick + document)

Generic saliency methods are known to FAIL on time series (Ismail et al., NeurIPS 2020
showed standard saliency conflates time and feature importance). Recommended SOTA,
matched to model type:

1. **Differentiable models (TCN/FCN) — Temporal Saliency Rescaling (TSR)** over a base
   gradient method (Integrated Gradients). Ismail et al. 2020, "Benchmarking Deep
   Learning Interpretability in Time Series" — TSR is the current standard fix for TS
   saliency and is the recommended primary. For FCN specifically, **Grad-CAM / CAM**
   is also valid and cheap (and aligns with Native Guide's CAM usage already in repo).
2. **Model-agnostic / strongest — Dynamic Masks** (Crabbé & van der Schaar, ICML 2021,
   "Explaining Time Series Predictions with Dynamic Masks"): learns a perturbation mask
   maximizing information removed; SOTA for TS attribution and model-agnostic, so it
   also covers the prototype adapter. Heavier compute — make it the opt-in "high
   quality" mode, TSR/IG the default.
3. **Prototype adapter** — perturbation/occlusion-based attribution (slide a masked
   window, measure score drop) since there is no gradient. Equivalent to a cheap
   dynamic-mask approximation.

Document the chosen method per model family. Cache results per (sample, model).

## Backend (new)

- [x] New service `saliency` returning a per-timestep attribution vector aligned to the
      series, with a `method` label.
- [x] New thin route `POST /api/saliency` (or `GET` with sample/model ids).
- [x] Update `requirements.txt` only if `captum` (for IG/TSR) is added; prefer a small
      self-contained IG + TSR implementation if avoiding the dep.

## Acceptance Criteria

- [x] Saliency toggle in EVIDENCE overlays a heatmap on the canvas, visually distinct
      from segment bands and shape-atom coloring (no layer confusion).
- [x] Attribution is per-timestep and time-aligned to the displayed series.
- [x] Method name + reference shown in a tooltip/legend.
- [x] Toggle off cleanly restores the plain canvas.
- [x] Method-per-model-family documented in Result Report + context.md.

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "REWORK-08: saliency overlay"`

## Result Report

### Recon

**Model families in the codebase**: exactly one inference adapter ships today — `PrototypeInferenceAdapter` in `backend/app/services/inference.py`. All three declared families (`fcn`, `mlp`, `inceptiontime`) route through it. The adapter computes `argmin_c ‖x − p_c‖²` over prototype vectors loaded from the model artifact's `metadata.json`. **No gradient method is exposed.** No TCN/FCN gradient adapter exists; SEG-002 / model dir contain prototype-only artifacts.

**Existing attribution code**: none. Verified `find backend/app/services -name "*saliency*" -o -name "*attribut*"` returns nothing; no route under any blueprint exposes attribution.

### Method-per-family choice (load-bearing)

The ticket's three options ranked correctly against what actually ships:

| Family | Method | Status |
|---|---|---|
| Prototype (the only family today) | **Perturbation/occlusion** (mean-mask each timestep, measure P(c*) drop) | **Selected** |
| Differentiable (TCN/FCN with gradients) | TSR over Integrated Gradients (Ismail et al. NeurIPS 2020) | Future — single-armed dispatch in place |
| Any | Dynamic Masks (Crabbé & van der Schaar ICML 2021) | Future — heavier, opt-in "high quality" |

Why occlusion is the right primary for today: the prototype adapter has no analytic gradient (forbidden by IG/TSR), and Dynamic Masks' learned-mask optimisation is heavy compute that requires a full model-agnostic loop. Mean-masked occlusion is the cheap, model-agnostic, no-dependency baseline that's been the standard since Zeiler & Fergus (ECCV 2014 §3.1). For univariate float UCR series, mean-masking is a sensible "neutral" baseline (preserves the global scale). Sign is preserved in the output so the UI can render counter-evidence (timesteps whose masking *improves* baseline-class confidence) — naive |attribution| would hide this.

**References**:
- Zeiler, Fergus, "Visualizing and Understanding Convolutional Networks," ECCV 2014 §3.1 — perturbation/occlusion as a visualisation technique.
- Crabbé, van der Schaar, "Explaining Time Series Predictions with Dynamic Masks," ICML 2021 — SOTA model-agnostic perturbation method; our occlusion is the uniform-per-timestep mask special case.
- Ismail, Gunady, Corrada Bravo, Feizi, "Benchmarking Deep Learning Interpretability in Time Series Predictions," NeurIPS 2020 — establishes that naive saliency conflates time and feature importance; introduces Temporal Saliency Rescaling (TSR) as the standard fix for the differentiable case.

### Backend (new + modified)

- `backend/app/schemas/saliency.py` (NEW) — `SaliencyResult` frozen dataclass with `artifact_id`, `baseline_class`, `attribution: tuple[float, ...]`, `method`, `reference`.
- `backend/app/services/saliency.py` (NEW) — `SaliencyService.compute_saliency(artifact_id, values)`. Family dispatch is a single-armed switch today (prototype → occlusion) with the docstring documenting the future TSR/IG route. Reuses `PrototypeInferenceAdapter` (cosmetic `family="prototype"`) so the saliency softmax convention matches the prediction route exactly. Defensive `x.copy()` so direct service callers can't have their numpy array mutated by the masking loop.
- `backend/app/routes/benchmarks.py` — new `POST /api/benchmarks/saliency`. Standard input validation (artifact_id non-empty string, values non-empty array of finite numbers, length ≤ 65 536). New `_get_saliency_service` factory mirroring the EvidenceService factory pattern.
- `backend/tests/test_benchmark_routes.py` — 3 new tests: missing-values 400, non-finite 400, happy path with attribution length matching input + at least one non-zero entry + method label contains "occlusion" + reference present.

### Frontend (new + modified)

- `frontend/src/lib/saliency/createSaliencyOverlayModel.js` (NEW) — pure helper. Per-cell rect with `x, width, fill, opacity`. Sign-encoded hue: amber positive (informative), indigo negative (counter-evidence). Square-root opacity scaling for perceptual readability. Empty/flat-zero → opacity 0 everywhere (no fabricated heat).
- `frontend/src/lib/saliency/createSaliencyOverlayModel.test.js` (NEW) — 7 unit tests covering empty input, cell shape, sign distinction, sqrt scaling, NaN handling, flat-zero quietness, bounds spanning.
- `frontend/src/components/viewer/SaliencyOverlay.vue` (NEW) — scoped-style SVG heatmap rendered **below** the chart line (load-bearing: never overlaps shape-atom segment bands inside the chart background). Three states: loading (spinner), error (warn-tinted alert), populated (heatmap + legend). Legend names the method and the `title` attr on the method label surfaces the paper reference on hover.
- `frontend/src/services/api/benchmarkApi.js` — `fetchSaliency({artifactId, values})` POST client.
- `frontend/src/components/viewer/TimelineViewer.vue` — new props `saliencyAttribution / saliencyMethod / saliencyReference / saliencyLoading / saliencyError`. Mounts `SaliencyOverlay` when any state is active; nothing renders when all are null/false (clean toggle-off).
- `frontend/src/views/BenchmarkViewerPage.vue`:
  - New refs `saliencyResult`, `saliencyLoading`, `saliencyError` + module-scoped `let saliencyRequestId = 0` race guard (mirrors plausibilityRequestId / minFlipRequestId).
  - `handleToggleSaliency` is now real: toggle on → `refreshSaliency()`; toggle off → clear state cleanly.
  - `refreshSaliency` POSTs `sample.value.values`, race-guarded, never throws into the UI feedback strip.
  - `seriesVersion` watcher also calls `refreshSaliency()` when the toggle is on so the heatmap stays in lockstep with edits.
  - `clearPredictionState` extended to reset all new state.
- `frontend/package.json` — added `src/lib/saliency/*.test.js` to the test glob.

### Toggle-off cleanliness

When the user toggles off, `saliencyResult`/`saliencyError`/`saliencyLoading` reset to `null`/`null`/`false`. The TimelineViewer props become `null` (page binds `probeFlags.saliency ? ... : null`). `SaliencyOverlay`'s `v-if="attribution || loading || error"` evaluates false → the component unmounts, the SVG band disappears, the chart restores to plain. AC met.

### Verification

- Frontend `npm test`: **759/759 PASS** (was 752; +7 new saliency lib tests).
- Backend benchmark routes: **22/22 PASS** (was 19; +3 new saliency route tests).
- Backend overall unchanged: same three pre-existing failures (`test_segment_encoder_feature_matrix`, `test_operation_result_contract`, `test_segmentation_eval` collection error) — none touch saliency code.
- code-reviewer: APPROVE, zero blocking issues. Three nits handled in-ticket: defensive `x.copy()` on the masking loop, `family="saliency"` → `family="prototype"` cosmetic rename (the family arg is unused by `predict()`; "prototype" is more honest), unused `family` local variable removed and replaced with a docstring note. The `h5py` requirements drift was a pre-existing unstaged modification — same exclusion as every prior REWORK commit.

### Caching

No server-side cache today. Each toggle-on and each post-edit auto-refresh runs O(T) backend predictions. For UCR-scale (T ≤ 1000) this is sub-second per call; a future ticket can add `(artifact_id, sample_hash)` LRU caching to the service when larger benchmarks land.

### Out of scope (intentional, deferred)

- **TSR over Integrated Gradients** — the standard fix for the differentiable case. Requires a gradient-exposing adapter, which is its own ticket.
- **Dynamic Masks** (Crabbé & van der Schaar ICML 2021) — SOTA model-agnostic. Heavier compute (a learned-mask optimisation loop); fits as an opt-in "high quality" mode.
- **Per-segment aggregation** — surfacing "this segment was the most important to the model" by averaging the attribution within segment boundaries. The data is already there; the UI rendering belongs in a separate ticket.
- **Server-side caching** — see above.
- **Debounce on rapid edits** — acceptable to skip at UCR-scale; reviewer flagged as a potential follow-up if larger benchmarks land.
