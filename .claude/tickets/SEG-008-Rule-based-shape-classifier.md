# SEG-008 — Rule-based shape classifier (cold-start)

**Status:** [x] Done
**Depends on:** SEG-001, SEG-010 (calibrated thresholds)

---

## Goal

Replace the Phi-4-mini cold-start classifier (SEG-007) with a **deterministic rule-based shape classifier** over the 7-primitive shape vocabulary `{plateau, trend, step, spike, cycle, transient, noise}`. The classifier emits per-class calibrated scores in [0, 1] and returns the argmax label plus a confidence value.

**Why:** Evidence from [[_project HypotheX-TS/HypotheX-TS - Literature Review - LLM Time Series Labeling|literature review]] shows that sub-4B text-only LLMs like Phi-4-mini fail structurally at periodicity detection and oscillation counting on time-series inputs (F1 ceiling 0.15–0.26 on UCR-style TSC). Classical primitives (Catch22, FFT, peak detection, STL residual) are faster, deterministic, and more accurate on this specific shape vocabulary.

**How it fits:** This is a cold-start labeler used before any user corrections exist. After `adapt_model` accumulates enough user corrections per class, the prototype classifier (SEG-011) takes over. The rule-based classifier is also invoked by the relabeler (OP-040) on the `RECLASSIFY_VIA_SEGMENTER` rule class path.

**Replaces:** SEG-007 as the default `use_llm_cold_start=False` path. SEG-007 remains available behind a flag for research/ablation but is no longer the product default.

---

## Architecture

```
X_seg (segment values)
  + ctx_pre, ctx_post (neighbour context windows)
    → compute primitives:
        slope, sign_consistency         (Theil-Sen)
        var, residual_to_line
        fft_peak, acf_peak              (periodicity)
        z_max, peak_width               (spike score)
        step_magnitude                  (mu(post) - mu(pre))
        catch22_features                (pycatch22)
    → per-class gate functions → q[y] ∈ [0, 1] for y in Y_shape
    → softmax(q) + argmax → (label, confidence, per_class_scores)
```

Thresholds `{τ_slope, τ_var, τ_per, τ_peak, τ_step, τ_ctx, τ_sign, τ_lin, τ_trans, L_spike_max}` are loaded from the calibrated YAML produced by SEG-010.

---

## Paper references (for `algorithm-auditor`)

- Lubba, Sethi, Knaute, Schultz, Fulcher, Jones (2019) "Catch22: CAnonical Time-series CHaracteristics" — *Data Min. Knowl. Discov.* 33:1821–1852. Library: `pycatch22`.
- Cleveland, Cleveland, McRae, Terpenning (1990) "STL: A Seasonal-Trend Decomposition Procedure" — *J. Official Statistics* 6(1):3–73.
- Truong, Oudre, Vayatis (2020) "Selective review of offline change-point detection methods" — *Signal Processing* 167:107299.

---

## Pseudocode

```python
def classify_shape(X_seg, ctx_pre, ctx_post, thresholds):
    slope, sign_cons = theil_sen(X_seg)
    var = np.var(X_seg)
    residual_lin = residual_to_line(X_seg, slope)
    fft_peak, acf_peak = spectral_peaks(X_seg)
    z_max, peak_w = peak_score(X_seg, ctx_pre, ctx_post)
    step_mag = np.mean(ctx_post) - np.mean(ctx_pre)
    c22 = pycatch22.catch22_all(X_seg.tolist())

    q = {}
    q['plateau']   = gate(abs(slope) < τ.slope, var < τ.var, acf_peak < τ.per)
    q['trend']     = gate(abs(slope) >= τ.slope, sign_cons >= τ.sign, residual_lin <= τ.lin)
    q['step']      = gate(abs(step_mag) >= τ.step, transition_time(X_seg) < τ.trans)
    q['spike']     = gate(len(X_seg) <= L_spike_max, z_max >= τ.peak,
                          context_contrast(X_seg, ctx_pre, ctx_post) >= τ.ctx)
    q['cycle']     = gate(len(X_seg) >= 2 * estimated_period(X_seg), acf_peak >= τ.per)
    q['transient'] = exp(-residual_log_exp_bump_fit(X_seg) / τ.trans)
    q['noise']     = ljung_box_whiteness(X_seg)   # p-value in [0, 1]

    scores = softmax(list(q.values()))
    label  = max(q, key=q.get)
    conf   = scores[list(q.keys()).index(label)]
    return ShapeLabel(label=label, confidence=conf, per_class_scores=q)
```

---

## Acceptance Criteria

- [ ] `backend/app/services/suggestion/rule_classifier.py` with:
  - `ShapeLabel` frozen dataclass: `label: str`, `confidence: float`, `per_class_scores: dict[str, float]`
  - `RuleBasedShapeClassifier` class loading thresholds from YAML on init
  - `classify_shape(X_seg, ctx_pre, ctx_post) -> ShapeLabel` — deterministic, same input → same output bit-identical
  - All 7 shape classes produce a score in [0, 1]
  - Returns `"noise"` with `confidence=1.0` as safe fallback if `len(X_seg) < 3`
- [ ] Per-class gate functions as separate helpers (unit-testable): `_plateau_gate`, `_trend_gate`, `_step_gate`, `_spike_gate`, `_cycle_gate`, `_transient_gate`, `_noise_gate`
- [ ] Helper `_spectral_peaks(X) -> (fft_peak, acf_peak)` using `scipy.fft` + autocorrelation; no external periodicity library beyond scipy
- [ ] `catch22` features via `pycatch22.catch22_all()` — only `DN_HistogramMode_5`, `SB_MotifThree_quantile_hh`, `CO_f1ecac` used in current gates; rest available for future ablation
- [ ] Thresholds loaded from `backend/app/services/suggestion/shape_thresholds.yaml` (version-pinned); fallback hardcoded defaults match those in the YAML
- [ ] `BoundarySuggestionService.propose()` uses `RuleBasedShapeClassifier` when `use_llm_cold_start=False` (the new default) and no user corrections exist yet
- [ ] Performance: `classify_shape` runs in ≤ 50 ms on a 1000-sample window on reference hardware (M-class or i7 equivalent)
- [ ] Synthetic benchmark fixture `backend/tests/fixtures/synthetic_shapes.py` generates ≥ 30 examples per shape class with known parameters
- [ ] Classification accuracy ≥ 85 % on the synthetic benchmark (held-out 20 %)
- [ ] `pycatch22` added to `backend/requirements.txt`
- [ ] Tests cover: each gate function (7), argmax path (1 per shape class), fallback for short segments, deterministic-output property (same input twice → identical output), threshold loading, performance budget

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass, coverage ≥ 90 % on new module
- [ ] Run `algorithm-auditor` agent with paper references: Lubba 2019 (Catch22 feature correctness), Cleveland 1990 (STL residual + periodicity), Truong 2020 (change-point primitive equivalence). Confirm: (a) each gate implements its cited formula correctly; (b) no SOTA drift that invalidates rule-based approach
- [ ] Run `code-reviewer` agent — no blocking issues, no logic in route handlers
- [ ] `git commit -m "SEG-008: rule-based shape classifier over 7-primitive vocabulary"`
- [ ] Update Status to `[x] Done`

## Work Done

- `backend/app/services/suggestion/rule_classifier.py` — `RuleBasedShapeClassifier`, `ShapeLabel` dataclass, 7 per-class gate helpers, Theil-Sen slope with range normalisation, ACF+FFT spectral peaks, variance-ratio transition detector, Catch22 wrapper, `_exp_bump_score` with fall-return check
- `backend/app/services/suggestion/shape_thresholds.yaml` — version-pinned threshold YAML; fallback hardcoded defaults match
- `backend/app/services/suggestions.py` — `_label_segments_with_rule_classifier` wired as default cold-start path; 7-primitive-to-domain label map; `import numpy as np` added
- `backend/tests/test_rule_classifier.py` — 49 tests: 7 gate functions, 8 argmax paths, 4 short-segment fallbacks, 2 determinism checks, 4 threshold-loading cases, 1 perf budget, 1 accuracy benchmark (97.1% on held-out synthetic shapes)
- `backend/tests/fixtures/synthetic_shapes.py` — 50 labelled examples per class (7 classes), deterministic seed
- `backend/requirements.txt` — added `scipy>=1.11.0`, `pycatch22>=0.4.2`, `PyYAML>=6.0`


---
