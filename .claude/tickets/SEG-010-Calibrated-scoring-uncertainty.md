# SEG-010 — Calibrated shape scoring + uncertainty margin

**Status:** [x] Done
**Depends on:** SEG-008 primitives; validation dataset

---

## Goal

Calibrate the shape-classifier thresholds `{τ_slope, τ_var, τ_per, τ_peak, τ_step, τ_ctx, τ_sign, τ_lin, τ_trans, L_spike_max, L_min}` from a small validation set using robust percentiles. Expose a margin-based uncertainty flag used by the UI to nudge users toward confirmation on ambiguous segments.

**Why:** Hardcoded thresholds hide domain assumptions and fail silently on out-of-domain series. Calibration from labeled data gives reproducible, auditable thresholds per dataset; the margin flag quantifies classifier uncertainty as `(max_q - second_max_q) < δ` and surfaces it to the user.

**How it fits:** Runs offline to produce `backend/app/services/suggestion/shape_thresholds.yaml` consumed by SEG-008 at runtime. The uncertainty-margin check runs inline in the classifier and stamps each `ShapeLabel` with an `uncertain: bool` flag that UI-004 and UI-013 read.

---

## Paper references (for `algorithm-auditor`)

- Platt (1999) "Probabilistic outputs for SVMs" — *Large-Margin Classifiers*, pp. 61–74.
- Niculescu-Mizil & Caruana (2005) "Predicting good probabilities with supervised learning" — *ICML 2005*.
- Bevis & Brown (2014) for domain-specific threshold examples in geodesy — *J. Geodesy* 88:283.

---

## Pseudocode

```python
def calibrate_thresholds(validation_set, percentile_config):
    """
    validation_set: list of (X_seg, ctx_pre, ctx_post, shape_label)
    percentile_config: dict specifying which quantile per primitive
    """
    by_class = defaultdict(list)
    for seg in validation_set:
        primitives = compute_primitives(seg.X, seg.ctx_pre, seg.ctx_post)
        by_class[seg.shape_label].append(primitives)

    return {
        'slope':  np.quantile([p.abs_slope for p in by_class['trend']],    q=0.1),
        'peak':   np.quantile([p.z_max    for p in by_class['spike']],    q=0.1),
        'per':    np.quantile([p.acf_peak for p in by_class['cycle']],    q=0.1),
        'step':   np.quantile([p.abs_step for p in by_class['step']],     q=0.1),
        'var':    np.quantile([p.var      for p in by_class['plateau']],  q=0.9),
        # ... one per threshold
    }

def uncertainty_margin(scores: dict, delta: float = 0.15) -> bool:
    sorted_q = sorted(scores.values(), reverse=True)
    return (sorted_q[0] - sorted_q[1]) < delta
```

---

## Acceptance Criteria

- [ ] `backend/scripts/calibrate_shape_thresholds.py` script reproducibly calibrates from `benchmarks/datasets/shape_calibration/`
- [ ] Output YAML `backend/app/services/suggestion/shape_thresholds.yaml` with version pin, calibration date, dataset checksum, and threshold dict
- [ ] Calibration is deterministic given a fixed validation dataset — snapshot test asserts bit-identical output
- [ ] `RuleBasedShapeClassifier` (SEG-008) loads thresholds at init; raises if YAML missing
- [ ] `ShapeLabel.uncertain: bool` field populated by `uncertainty_margin(per_class_scores, delta=0.15)`
- [ ] Classifier accuracy on held-out set does not drop more than 2 pts vs hand-tuned baseline (measured via SEG-006 eval harness)
- [ ] Uncertain-flag rate on held-out set between 5 % and 20 % (if higher, thresholds are too loose and calibration needs wider quantile)
- [ ] Delta parameter `uncertainty_delta` exposed in config, default 0.15
- [ ] Tests cover: YAML round-trip, threshold values are positive finite floats, uncertainty_margin edge cases (all equal scores, single-class input)
- [ ] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper references: Platt 1999 (calibration methodology), Niculescu-Mizil 2005 (robust percentiles vs Platt vs isotonic). Confirm thresholds set from labeled data (not unlabeled heuristics); robust-percentile choice justified over mean ± k·std
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "SEG-010: calibrated shape-scoring thresholds + uncertainty-margin flag"`
- [ ] Update Status to `[x] Done`

## Work Done

- `backend/app/services/suggestion/rule_classifier.py` — added `uncertain: bool = False` to `ShapeLabel`; added module-level `uncertainty_margin(scores, delta)` function; added `"uncertainty_delta": 0.15` to `_DEFAULT_THRESHOLDS`; `RuleBasedShapeClassifier.__init__` now reads `self._uncertainty_delta` from loaded thresholds; `classify_shape()` sets `uncertain` flag via `uncertainty_margin`
- `backend/app/services/suggestion/shape_thresholds.yaml` — added `uncertainty_delta: 0.15` threshold entry
- `backend/scripts/calibrate_shape_thresholds.py` — calibration script: reads labeled CSV, computes gate primitives per class, applies robust percentiles (q=0.10 lower-bound / q=0.90 upper-bound), writes YAML with version, calibration_date, dataset_checksum; deterministic given fixed dataset
- `benchmarks/datasets/shape_calibration/shape_calibration_data.csv` — 350 labeled synthetic examples (50 per class, seed=42) used as calibration validation set
- `backend/tests/test_calibration.py` — 26 tests covering `uncertainty_margin` edge cases, `ShapeLabel.uncertain` field, YAML `uncertainty_delta` loading, calibration script structure/determinism/positive-finite-values


---
