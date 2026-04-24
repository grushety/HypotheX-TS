# SEG-014 — Decomposition fitter: STL / MSTL (cycles)

**Status:** [ ] Done
**Depends on:** SEG-019

---

## Goal

Fit STL (single period) or MSTL (multiple periods) decomposition to segments labeled `cycle`. Produces `{trend, seasonal_T, residual}` components editable by OP-024 Tier-2 cycle operations (amplitude scaling, phase shift, period change, harmonic content).

**Why:** STL is the canonical seasonal-trend decomposition for cyclic TS; its components are exactly what's needed to implement `amplify_amplitude`, `dampen_amplitude`, `phase_shift`, `deseasonalise_remove`, and `replace_with_flat` as coefficient edits rather than pointwise perturbations.

**How it fits:** Dispatched by SEG-019 when `shape == 'cycle'`. Single period → STL; multiple periods (hourly + daily + weekly + annual, etc.) → MSTL. Period(s) detected automatically via FFT + ACF if not supplied.

---

## Paper references (for `algorithm-auditor`)

- Cleveland, Cleveland, McRae, Terpenning (1990) "STL: A Seasonal-Trend Decomposition Procedure Based on Loess" — *J. Official Statistics* 6(1):3–73.
- Bandara, Hyndman, Bergmeir (2021) "MSTL: A Seasonal-Trend Decomposition Algorithm for Time Series with Multiple Seasonal Patterns" — *IJCNN 2021*. arXiv 2107.13462.
- Library: `statsmodels.tsa.seasonal.STL` and `statsmodels.tsa.seasonal.MSTL`.

---

## Pseudocode

```python
def fit_stl(X_seg, period=None, robust=True):
    if period is None:
        period = detect_dominant_period(X_seg)   # FFT + ACF fallback

    if isinstance(period, (int, float)):
        result = STL(X_seg, period=int(period), robust=robust).fit()
        components = {
            'trend':    result.trend,
            'seasonal': result.seasonal,
            'residual': result.resid,
        }
        method = 'STL'
    else:
        # MSTL with list of periods
        result = MSTL(X_seg, periods=[int(p) for p in period]).fit()
        components = {'trend': result.trend}
        for p in period:
            components[f'seasonal_{int(p)}'] = result.seasonal[f'seasonal_{int(p)}']
        components['residual'] = result.resid
        method = 'MSTL'

    return DecompositionBlob(
        method=method,
        components=components,
        coefficients={'period': period, 'robust': robust},
        residual=components['residual'],
        fit_metadata={'rmse': float(np.sqrt(np.mean(components['residual']**2)))}
    )
```

---

## Acceptance Criteria

- [ ] `backend/app/services/decomposition/stl_fitter.py` with:
  - `fit_stl(X_seg, period=None, robust=True) -> DecompositionBlob`
  - `detect_dominant_period(X) -> int | list[int]` using FFT peak + ACF confirmation
- [ ] `period` can be scalar (→ STL) or list (→ MSTL); both paths produce named `seasonal_T` components
- [ ] `robust=True` default (inner/outer loop with robust weights per Cleveland 1990 §3.5)
- [ ] Reassembled signal `trend + sum(seasonal_*) + residual` matches original within RMSE < 1e-10 (STL is exact up to numerical precision)
- [ ] OP-024 (Cycle ops) can edit `seasonal[T]` in place without changing method or other components
- [ ] Period detection: unit test with synthetic `sin(2πt/24) + sin(2πt/168) + noise` → detects [24, 168] (daily + weekly)
- [ ] Multivariate handling: fit per-component, stack coefficients
- [ ] Tests cover: single-period STL on synthetic `sin(2πt/12)`; multi-period MSTL on synthetic combined cycles; auto-detect period; robust mode flag honored; reassembly round-trip
- [ ] `statsmodels` version pin ≥ 0.14 in `backend/requirements.txt`
- [ ] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper references: Cleveland 1990 §2-3 (inner/outer loop, seasonal smoothing parameters), Bandara 2021 (MSTL iteration). Confirm robust weight iteration enabled; period auto-detection uses documented spectral+ACF approach
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "SEG-014: STL/MSTL decomposition fitter for cycle segments"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
