# OP-026 — Noise Tier-2 ops (5 ops)

**Status:** [x] Done
**Depends on:** OP-013 (add_uncertainty primitive), OP-040 (relabeler)

---

## Goal

Implement the 5 Noise-specific Tier-2 ops: `suppress_denoise`, `amplify`, `change_color`, `inject_synthetic`, `whiten`.

**How it fits:** Gated when active shape is `noise`. `suppress_denoise` → RECLASSIFY (may reveal trend/cycle/transient underneath). Others preserve noise.

---

## Paper references (for `algorithm-auditor`)

- Chang, Yu, Vetterli (2000) "Adaptive wavelet thresholding for image denoising and compression" — *IEEE T. Image Proc.* 9(9):1532–1546 (BayesShrink).
- Rudin, Osher, Fatemi (1992) "Nonlinear total variation based noise removal algorithms" — *Physica D* 60(1–4):259–268 (TV).
- Timmer & König (1995) — colored noise generation.
- Savitzky & Golay (1964) — SG smoothing.
- Yunjun, Fattahi, Amelung (2019) "Small baseline InSAR time series analysis" — *CAGEO* 133:104331 (GACOS/PyAPS).

---

## Acceptance Criteria

- [x] `backend/app/services/operations/tier2/noise.py` with all 5 ops
- [x] `suppress_denoise` supports ≥ 3 methods: BayesShrink (default), SG, TV; Kalman and GACOS optional
- [x] `change_color` preserves trend/cycle structure (uses detrended residual for noise replacement)
- [x] `inject_synthetic` accepts a `NoiseModel` object with `.sample(n)` method (AR(1), flicker, Gamma speckle models in `backend/app/services/noise_models/`)
- [x] `suppress_denoise` emits OP-040 RECLASSIFY (denoised signal shape depends on underlying structure)
- [x] `whiten` uses Welch PSD estimation + spectral-divide spiking deconvolution
- [x] `pywt` and `scikit-image` added to `backend/requirements.txt`
- [x] Tests cover: each denoising method on synthetic pink noise; spectral shape test for change_color (log-log PSD slope); round-trip inject + denoise recovers original within tolerance
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "OP-026: Noise Tier-2 ops (5 ops)"` ← hook auto-moves this file to `done/` on commit

## Result Report

Created `backend/app/services/operations/tier2/noise.py` with 5 ops. `suppress_denoise` takes raw ndarray (like spike ops) and supports BayesShrink (Chang 2000, sym8 wavelet, MAD-based threshold), SG, TV (Chambolle via scikit-image), Kalman-RTS smoother, and GACOS correction. The other 4 ops take `blob` and operate on `components['residual']` to preserve trend/cycle structure. `change_color` replaces residual with colored noise of the same σ via colorednoise. `inject_synthetic` adds `noise_model.sample(n)` to residual. `whiten` divides by sqrt(Welch PSD). Also created `backend/app/services/noise_models/` with `NoiseModel` Protocol + `AR1NoiseModel`, `FlickerNoiseModel`, `GammaSpeckleModel`. Key gotchas caught in review: (1) Kalman smoother silently produces NaN when `q=0` or `r=0` — added ValueError guards; (2) `whiten` silently produces NaN/Inf when residual is near-constant (PSD→0 → whitening→Inf) — added isfinite fallback to original residual; (3) `inject_synthetic` else-branch missing length check — added symmetrically. New deps: `PyWavelets>=1.4`, `scikit-image>=0.22`. 74 tests in `test_noise_ops.py`.
