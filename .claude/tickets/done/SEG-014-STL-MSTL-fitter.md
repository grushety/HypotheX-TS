# SEG-014 — Decomposition fitter: STL / MSTL (cycles)

**Status:** [x] Done
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

- [x] `backend/app/services/decomposition/fitters/stl.py` with:
  - `fit_stl(X_seg, period=None, robust=True) -> DecompositionBlob`
  - `detect_dominant_period(X) -> int | list[int]` using FFT peak + ACF confirmation
- [x] `period` can be scalar (→ STL) or list (→ MSTL); both paths produce named `seasonal_T` components
- [x] `robust=True` default (inner/outer loop with robust weights per Cleveland 1990 §3.5)
- [x] Reassembled signal `trend + sum(seasonal_*) + residual` matches original within RMSE < 1e-10 (STL is exact up to numerical precision)
- [x] OP-024 (Cycle ops) can edit `seasonal[T]` in place without changing method or other components
- [x] Period detection: unit test with synthetic `sin(2πt/24) + sin(2πt/168) + noise` → detects [24, 168] (daily + weekly)
- [x] Multivariate handling: fit per-component, stack coefficients
- [x] Tests cover: single-period STL on synthetic `sin(2πt/12)`; multi-period MSTL on synthetic combined cycles; auto-detect period; robust mode flag honored; reassembly round-trip
- [x] `statsmodels` version pin ≥ 0.14 in `backend/requirements.txt`
- [x] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass (37/37)
- [x] Run `code-reviewer` agent — 2 blocking issues found and fixed:
  1. MSTL seasonal column mislabeling for unsorted period input (sort `valid_periods` before naming)
  2. MSTL `UnboundLocalError` when segment too short for all periods (underdetermined fallback added)
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "SEG-014: STL/MSTL decomposition fitter for cycle segments"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

**Date:** 2026-04-26

**Implementation:** Replaced stubs in `backend/app/services/decomposition/fitters/stl.py` and `mstl.py` with full Cleveland (1990) STL and Bandara et al. (2021) MSTL implementations via statsmodels. Added `detect_dominant_period()` in `stl.py`: FFT power spectrum → round to integer periods with power ≥ 10 % threshold → ACF refinement (±5 lag window, > 0.10 confirmation) → returns `int` for single or `list[int]` for multiple dominant periods. MSTL `mstl.py` imports `detect_dominant_period` from `stl.py`; both fitters handle 1-D and multivariate (n, d) inputs. `statsmodels>=0.14` added to requirements.txt.

**Bugs found during review and fixed before commit:**
1. **MSTL column mislabeling**: statsmodels MSTL sorts periods internally; `valid_periods` must be sorted before iterating to name `seasonal_{T}` columns, otherwise unsorted period input (e.g. `[60, 12]`) produces reversed labels. Fixed by sorting `valid_periods`.
2. **MSTL underdetermined crash**: when all requested periods satisfy `2*period >= n`, statsmodels removes them all and raises `UnboundLocalError`. Fixed with an explicit underdetermined guard that returns a constant-mean fallback blob with `fit_metadata["underdetermined"] = True`.

**Tests:** 37/37 pass. Covers: `detect_dominant_period` (single, multi, noisy, too-short), STL reassembly exact (1e-10), STL robust flag, auto-detect period, residual storage, multivariate shapes, JSON round-trip, MSTL component naming, MSTL auto-detect daily+weekly, MSTL unsorted period regression, MSTL underdetermined fallback, dispatch integration.
