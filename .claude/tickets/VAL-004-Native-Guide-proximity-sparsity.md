# VAL-004 — Native-Guide proximity & sparsity (per-edit, fast path)

**Status:** [ ] Done
**Depends on:** OP-050

---

## Goal

For each edited series x', compute Native-Guide proximity (DTW distance to original x) and sparsity (fraction of unchanged time-steps). These are the canonical TS-CF "minimality" metrics from Delaney et al. ICCBR 2021.

**Why:** A CF that flips the prediction with the smallest, most local change is more interpretable. Proximity quantifies *how much* the series changed in absolute terms; sparsity quantifies *how localised* the change is. The two metrics are complementary — a low-proximity but dense edit is structurally different from a high-proximity but sparse edit.

**How it fits:** Fast-path metric. Pure functions over (x, x'). Triggers UI tip if sparsity < 0.7 AND DTW-proximity exceeds the 90th percentile of nearest-unlike-neighbour distances (calibrated offline per dataset).

---

## Paper references (for `algorithm-auditor`)

- Delaney, Greene, Keane, **"Instance-based Counterfactual Explanations for Time Series Classification,"** ICCBR 2021, LNCS 12877:32–47, DOI 10.1007/978-3-030-86957-1_3.
- Sakoe & Chiba (1978) — DTW band.

---

## Pseudocode

```python
def native_guide_proximity(x, x_prime, metric='dtw', dtw_band=0.1):
    if metric == 'dtw':
        from tslearn.metrics import dtw
        return dtw(x, x_prime, sakoe_chiba_radius=int(dtw_band * len(x)))
    elif metric == 'euclidean':
        return float(np.linalg.norm(x - x_prime))
    elif metric == 'l1':
        return float(np.sum(np.abs(x - x_prime)))

def native_guide_sparsity(x, x_prime, eps_per_dim=1e-6):
    # Fraction of time-steps where the edit is below noise floor
    diff = np.abs(x - x_prime)
    unchanged = np.sum(diff < eps_per_dim)
    return unchanged / len(x)

def native_guide_validate(x, x_prime, dataset_thresholds) -> NativeGuideResult:
    prox    = native_guide_proximity(x, x_prime, metric='dtw')
    sparse  = native_guide_sparsity(x, x_prime)
    return NativeGuideResult(
        proximity=prox,
        sparsity=sparse,
        proximity_pct=percentile_rank(prox, dataset_thresholds.nun_distances),
        too_dense=(sparse < 0.7 and prox > dataset_thresholds.q90_nun),
    )
```

---

## Acceptance Criteria

- [ ] `backend/app/services/validation/native_guide.py` with:
  - `NativeGuideResult` frozen dataclass: `proximity`, `sparsity`, `proximity_pct`, `too_dense: bool`
  - `native_guide_proximity` supporting `dtw` (default), `euclidean`, `l1`
  - `native_guide_sparsity` with configurable per-dim noise floor (default 1e-6 in normalised space)
  - `native_guide_validate(x, x_prime, dataset_thresholds)` producing the result struct
- [ ] Calibration script `scripts/calibrate_native_guide_thresholds.py` computes nearest-unlike-neighbour (NUN) distance distribution per dataset; stores 90th percentile in `dataset_thresholds.q90_nun`
- [ ] `too_dense=True` triggers UI tip "edit changed too much; try a more local edit" (VAL-020)
- [ ] Sparsity uses the SAME noise floor in normalised feature space across edits (no per-edit re-normalisation drift)
- [ ] Latency: ≤ 50 ms per call for series ≤ 10k samples (DTW with band)
- [ ] Stored in `CFResult.validation.native_guide`
- [ ] Tests: proximity zero on identity edit; sparsity = 1 on identity; large dense edit triggers `too_dense`; calibration deterministic
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper ref Delaney et al. ICCBR 2021. Confirm proximity uses DTW with band per Native Guide §3.2; sparsity definition matches paper Eq. 1; NUN-percentile threshold documented
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "VAL-004: Native-Guide proximity & sparsity (per-edit)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
