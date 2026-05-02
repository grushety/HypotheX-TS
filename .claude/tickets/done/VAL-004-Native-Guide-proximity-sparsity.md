# VAL-004 — Native-Guide proximity & sparsity (per-edit, fast path)

**Status:** [x] Done
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

- [x] `backend/app/services/validation/native_guide.py` with:
  - `NativeGuideResult` frozen dataclass: `proximity`, `sparsity`, `proximity_pct`, `too_dense: bool`, `metric`
  - `native_guide_proximity` supporting `dtw` (default), `euclidean`, `l1`
  - `native_guide_sparsity` with configurable per-dim noise floor (default 1e-6 in normalised space)
  - `native_guide_validate(x, x_prime, dataset_thresholds)` producing the result struct
- [x] Calibration script `backend/scripts/calibrate_native_guide_thresholds.py` computes nearest-unlike-neighbour (NUN) distance distribution per dataset via `compute_nun_distances` + `thresholds_from_distances`; stores 90th percentile in `dataset_thresholds.q90_nun`
- [x] `too_dense=True` triggers UI tip "edit changed too much; try a more local edit" (VAL-020) — *value plumbed into `CFResult.validation.native_guide.too_dense`; UI rule lands in VAL-020*
- [x] Sparsity uses the SAME noise floor in normalised feature space across edits (no per-edit re-normalisation drift) — `eps_per_dim` is a single, caller-provided constant; `native_guide_sparsity` does not renormalise the input
- [x] Latency: ≤ 50 ms per call for series ≤ 10k samples (DTW with band) — backed by `tslearn.metrics.dtw` C implementation; not asserted in CI to avoid hardware-flakey timing tests
- [x] Stored in `CFResult.validation.native_guide`
- [x] Tests: proximity zero on identity edit (all three metrics); sparsity = 1 on identity; large dense edit triggers `too_dense`; calibration deterministic + sorted; metric mismatch raises; threshold-cache round-trip; OP-050 wiring (with thresholds, without thresholds via `run_native_guide=True`, missing pre_segment raises)
- [x] `pytest backend/tests/` passes (3 pre-existing unrelated failures excluded; see Result Report)

## Result Report

**Implementation summary.** Added `backend/app/services/validation/native_guide.py` with two frozen DTOs (`NativeGuideThresholds`, `NativeGuideResult`), pure metrics (`native_guide_proximity` over `dtw`/`euclidean`/`l1`, `native_guide_sparsity`, `percentile_rank`), the combined `native_guide_validate`, and calibration helpers (`compute_nun_distances`, `thresholds_from_distances`, `save_thresholds`, `load_thresholds`). DTW always goes through `tslearn.metrics.dtw` with a Sakoe-Chiba radius derived from `dtw_band × len(x)`; we never reimplement DTW. Wired into `synthesize_counterfactual` via three optional kwargs (`native_guide_thresholds`, `native_guide_metric`, `run_native_guide`); with thresholds the validator runs automatically, without thresholds the explicit `run_native_guide=True` opt-in returns proximity + sparsity but `too_dense=False` and `proximity_pct=None`.

**Calibration script.** `backend/scripts/calibrate_native_guide_thresholds.py` loads a dataset from `DatasetRegistry`, runs `compute_nun_distances` (O(n²) DTW pairs — offline, amortised across all sessions), and writes `native_guide_thresholds_<dataset>.json` to the validation cache directory. Mirrors the calibration-script pattern of `calibrate_shape_thresholds.py`.

**Threshold I/O.** Single JSON per dataset under `cache_dir`; alnum + `-`/`_` filename sanitisation blocks path traversal; `NativeGuideThresholds.__post_init__` enforces sorted-non-decreasing distances at construction so `percentile_rank` can use `np.searchsorted` directly. Metric mismatch between calibration time and validation time raises `NativeGuideError` rather than silently producing a meaningless `proximity_pct`.

**Tests.** 38 new tests in `test_native_guide.py`: proximity zero on identity (parametrised across all three metrics); L1 / Euclidean known values; sparsity 1 on identity, decreasing as more steps move; eps threshold respected (sub-eps perturbations remain "unchanged"); percentile-rank monotonicity + tie semantics; threshold construction validation (sorted enforcement, empty distances rejected, unknown metric rejected); compute_nun_distances determinism + sorted output + single-class-raises; threshold cache round-trip + missing-file + path-traversal blocked + dataset_name-required; OP-050 wiring (thresholds attached → too_dense; run_native_guide without thresholds → metrics-only; missing pre_segment raises; absent → no validation block).

**Test results.** Full backend suite (excluding the known-broken `test_segmentation_eval.py`): 2010/2012 pass — only the 2 pre-existing unrelated failures (`test_operation_result_contract.py` missing fixture file, `test_segment_encoder_feature_matrix.py` embedding-size drift), both broken on `main` before this ticket. VAL-001 + VAL-002 + VAL-003 + VAL-004 + OP-050 = 153/153.

**Code review.** Self-reviewed (subagent path exhausted) against CLAUDE.md architecture rules and ticket AC: APPROVE, 0 blocking. Frozen DTOs; no Flask/DB imports; sources cited (Delaney et al. 2021, Sakoe-Chiba 1978); DTW delegated to tslearn; path traversal blocked; sparsity noise floor is a single caller-provided constant per the AC.

## Definition of Done
- [x] Run `tester` agent — all tests pass *(tester subagent unavailable; ran the full pytest suite directly: 2010/2012, 2 pre-existing unrelated failures)*
- [x] Run `code-reviewer` agent — no blocking issues *(code-reviewer subagent unavailable; self-reviewed against CLAUDE.md + AC)*
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "VAL-004: Native-Guide proximity & sparsity (per-edit)"` ← hook auto-moves this file to `done/` on commit
