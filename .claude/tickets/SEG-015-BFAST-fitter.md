# SEG-015 — Decomposition fitter: BFAST (EO breakpoints)

**Status:** [ ] Done
**Depends on:** SEG-019, SEG-014 (STL interop)

---

## Goal

Fit BFAST (Breaks For Additive Season and Trend) decomposition for remote-sensing time series containing breakpoints. Produces `{trend, seasonal, breakpoints, remainder}` with break magnitudes stored as editable coefficients.

**Why:** BFAST is the canonical EO disturbance-detection decomposition; breakpoints correspond to the `step` shape in HypotheX-TS vocabulary, and the trend/seasonal split maps onto `trend` and `cycle` shapes. User-editable breakpoints are essential for the `disturbance` and `recovery` semantic labels in the remote-sensing pack (SEG-023).

**How it fits:** Dispatched by SEG-019 when `domain_hint='remote-sensing'` and the segment contains at least one candidate breakpoint from SEG-009. Used by OP-022 (Step ops) and OP-023 semantic pack (SEG-023) to enable edits like `de_jump(disturbance)` or `shift_in_time(recovery_onset)`.

---

## Paper references (for `algorithm-auditor`)

- Verbesselt, Hyndman, Newnham, Culvenor (2010) "Detecting trend and seasonal changes in satellite image time series" — *Remote Sensing of Environment* 114(1):106–115. DOI 10.1016/j.rse.2009.08.014.
- Verbesselt, Zeileis, Herold (2012) "Near real-time disturbance detection using satellite image time series" — *RSE* 123:98–108.
- Masiliūnas, Tsendbazar, Herold, Verbesselt (2021) "BFAST Lite: a lightweight break detection method for time series analysis" — *Remote Sensing* 13(16):3308 (Lite variant).

---

## Pseudocode

```python
def fit_bfast(X_seg, t, period, h=0.15, max_iter=10):
    """
    h: minimum segment size as fraction of series length (Verbesselt 2010 §2)
    """
    Tt = np.zeros_like(X_seg)
    St = np.zeros_like(X_seg)
    breakpoints = []

    for iteration in range(max_iter):
        # Fit seasonal component on detrended series
        St = fit_seasonal_dummies(X_seg - Tt, period)

        # Fit trend with breakpoint detection via OLS-MOSUM + F-test
        Tt_new, new_breaks = fit_trend_with_bp(X_seg - St, h=h)

        if converged(Tt, Tt_new):
            Tt = Tt_new
            breakpoints = new_breaks
            break
        Tt = Tt_new
        breakpoints = new_breaks

    remainder = X_seg - Tt - St
    break_magnitudes = [magnitude_at(Tt, bp) for bp in breakpoints]

    return DecompositionBlob(
        method='BFAST',
        components={
            'trend':       Tt,
            'seasonal':    St,
            'remainder':   remainder,
            'breakpoints': breakpoints,
        },
        coefficients={
            'break_epochs':     breakpoints,
            'break_magnitudes': break_magnitudes,
            'period':           period,
            'h':                h,
        },
        residual=remainder,
        fit_metadata={'n_breakpoints': len(breakpoints),
                      'rmse': float(np.sqrt(np.mean(remainder**2)))}
    )
```

---

## Acceptance Criteria

- [ ] `backend/app/services/decomposition/bfast_fitter.py` with:
  - `fit_bfast(X_seg, t, period, h=0.15, max_iter=10) -> DecompositionBlob`
  - `fit_trend_with_bp(X, h)` helper using OLS-MOSUM (Chu-Hornik-Kuan) + F-test per Verbesselt 2010 §2
  - `fit_seasonal_dummies(X, period)` helper using harmonic regression
- [ ] Both classical (Verbesselt 2010) and Lite (Masiliūnas 2021) modes available via `variant: Literal['classical', 'lite'] = 'classical'`
- [ ] `h` parameter respected; minimum segment size between breakpoints = `h * len(X_seg)`
- [ ] Unit test: synthetic NDVI-like series `seasonal + trend_segment_1 → trend_segment_2` with known breakpoint at t=180 → detected within ±3 timesteps
- [ ] Reassembled signal `trend + seasonal + remainder = X_seg` within numerical precision
- [ ] Break epochs and magnitudes stored as coefficients; OP-022 (Step ops) reads and edits these directly
- [ ] Iterative fit converges within `max_iter`; non-convergence logs warning but returns best-so-far
- [ ] Compatible with SEG-014 STL output format (same component naming for `trend`, `seasonal`, `residual`)
- [ ] Tests cover: breakpoint detection accuracy, h-parameter effect on minimum segment size, convergence, variant switch, reassembly round-trip
- [ ] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper references: Verbesselt 2010 §2 (iterative STL + OLS-MOSUM), Verbesselt 2012 (near-real-time), Masiliūnas 2021 (Lite). Confirm F-test correctly implemented; `h` matches paper definition; seasonal-trend alternation converges
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "SEG-015: BFAST decomposition fitter for EO breakpoints"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
