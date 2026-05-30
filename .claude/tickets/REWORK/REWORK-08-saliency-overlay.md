# REWORK-08 — Saliency overlay (where the model is looking)

**Status:** [ ] Done
**Depends on:** REWORK-01

---

## Goal

Add a toggleable attribution heatmap ON the series canvas, suggesting *where* the
model is looking — framed as a suggestion the what-if then verifies (attribution
proposes, editing confirms). Net-new backend: no saliency/attribution code currently
exists in the repo (verified — `services/` has no attribution module).

---

## Task 0 — Recon (record in Result Report)

- [ ] Confirm model type(s) behind the active benchmarks: prototype adapter
      (`inference.py`) and any TCN/FCN artifacts (SEG-002, model dir). Document which
      are differentiable (gradient methods available) vs. distance-based (prototype —
      needs perturbation-based attribution).
- [ ] Confirm there is no existing attribution endpoint.

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

- [ ] New service `saliency` returning a per-timestep attribution vector aligned to the
      series, with a `method` label.
- [ ] New thin route `POST /api/saliency` (or `GET` with sample/model ids).
- [ ] Update `requirements.txt` only if `captum` (for IG/TSR) is added; prefer a small
      self-contained IG + TSR implementation if avoiding the dep.

## Acceptance Criteria

- [ ] Saliency toggle in EVIDENCE overlays a heatmap on the canvas, visually distinct
      from segment bands and shape-atom coloring (no layer confusion).
- [ ] Attribution is per-timestep and time-aligned to the displayed series.
- [ ] Method name + reference shown in a tooltip/legend.
- [ ] Toggle off cleanly restores the plain canvas.
- [ ] Method-per-model-family documented in Result Report + context.md.

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "REWORK-08: saliency overlay"`

## Result Report
<!-- method per model family + references, caching, files touched -->
