# OP-026 — Noise Tier-2 ops (5 ops)

**Status:** [ ] Done
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

## Pseudocode

```python
def suppress_denoise(X_seg, method: Literal['bayesshrink', 'sg', 'kalman', 'tv', 'gacos'] = 'bayesshrink',
                     **kwargs):
    if method == 'bayesshrink':
        import pywt
        coeffs = pywt.wavedec(X_seg, 'sym8')
        # BayesShrink soft-threshold (Chang 2000)
        sigma = np.median(np.abs(coeffs[-1])) / 0.6745
        threshold = sigma ** 2 / np.sqrt(max(np.var(X_seg) - sigma ** 2, 1e-12))
        coeffs = [coeffs[0]] + [pywt.threshold(c, threshold, mode='soft') for c in coeffs[1:]]
        return pywt.waverec(coeffs, 'sym8')[:len(X_seg)]
    elif method == 'sg':
        from scipy.signal import savgol_filter
        return savgol_filter(X_seg, kwargs.get('window', 11), kwargs.get('poly', 3))
    elif method == 'kalman':
        return kalman_rts_smoother(X_seg, **kwargs)
    elif method == 'tv':
        from skimage.restoration import denoise_tv_chambolle
        return denoise_tv_chambolle(X_seg, weight=kwargs.get('weight', 0.1))
    elif method == 'gacos':
        return X_seg - kwargs['gacos_correction']

def amplify(blob, alpha):
    if 'residual' in blob.components:
        blob.components['residual'] *= alpha
    return blob.reassemble()

def change_color(X_seg, target_color: Literal['white', 'pink', 'red']):
    from colorednoise import powerlaw_psd_gaussian
    detrended = X_seg - np.mean(X_seg)
    sigma = np.std(detrended)
    beta = {'white': 0.0, 'pink': 1.0, 'red': 2.0}[target_color]
    new_noise = powerlaw_psd_gaussian(beta, len(X_seg)) * sigma
    return np.mean(X_seg) + new_noise

def inject_synthetic(X_seg, noise_model):
    synthetic = noise_model.sample(len(X_seg))
    return X_seg + synthetic

def whiten(X_seg):
    from scipy.signal import welch
    f, psd = welch(X_seg)
    # Spiking deconvolution: divide by sqrt(PSD) in frequency domain
    spectrum = np.fft.rfft(X_seg)
    whitening = 1.0 / (np.sqrt(np.interp(np.fft.rfftfreq(len(X_seg)), f, psd)) + 1e-12)
    return np.fft.irfft(spectrum * whitening, n=len(X_seg))
```

---

## Acceptance Criteria

- [ ] `backend/app/services/operations/tier2/noise.py` with all 5 ops
- [ ] `suppress_denoise` supports ≥ 3 methods: BayesShrink (default), SG, TV; Kalman and GACOS optional
- [ ] `change_color` preserves trend/cycle structure (uses detrended residual for noise replacement)
- [ ] `inject_synthetic` accepts a `NoiseModel` object with `.sample(n)` method (AR(1), flicker, Gamma speckle models in `backend/app/services/noise_models/`)
- [ ] `suppress_denoise` emits OP-040 RECLASSIFY (denoised signal shape depends on underlying structure)
- [ ] `whiten` uses Welch PSD estimation + spectral-divide spiking deconvolution
- [ ] `pywt` and `scikit-image` added to `backend/requirements.txt`
- [ ] Tests cover: each denoising method on synthetic pink noise; spectral shape test for change_color (log-log PSD slope); round-trip inject + denoise recovers original within tolerance
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "OP-026: Noise Tier-2 ops (5 ops)"` ← hook auto-moves this file to `done/` on commit
