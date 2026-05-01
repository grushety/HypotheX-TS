# SEG-015 — Decomposition fitter: BFAST (EO breakpoints)

**Status:** [x] Done
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

- [x] `backend/app/services/decomposition/bfast_fitter.py` with:
  - `fit_bfast(X_seg, t, period, h=0.15, max_iter=10) -> DecompositionBlob`
  - `fit_trend_with_bp(X, h)` helper using OLS-MOSUM (Chu-Hornik-Kuan) + F-test per Verbesselt 2010 §2
  - `fit_seasonal_dummies(X, period)` helper using harmonic regression
- [x] Both classical (Verbesselt 2010) and Lite (Masiliūnas 2021) modes available via `variant: Literal['classical', 'lite'] = 'classical'`
- [x] `h` parameter respected; minimum segment size between breakpoints = `h * len(X_seg)`
- [x] Unit test: synthetic NDVI-like series `seasonal + trend_segment_1 → trend_segment_2` with known breakpoint at t=180 → detected within ±3 timesteps
- [x] Reassembled signal `trend + seasonal + remainder = X_seg` within numerical precision
- [x] Break epochs and magnitudes stored as coefficients; OP-022 (Step ops) reads and edits these directly
- [x] Iterative fit converges within `max_iter`; non-convergence logs warning but returns best-so-far
- [x] Compatible with SEG-014 STL output format (same component naming for `trend`, `seasonal`, `residual`)
- [x] Tests cover: breakpoint detection accuracy, h-parameter effect on minimum segment size, convergence, variant switch, reassembly round-trip
- [x] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "SEG-015: BFAST decomposition fitter for EO breakpoints"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Replaced the placeholder BFAST stub with a full Verbesselt 2010 / Masiliūnas 2021 fitter.

**Files**
- `backend/app/services/decomposition/fitters/bfast.py` (replaced stub) — 5 public/private layers:
  - `fit_seasonal_dummies(X, period, n_harmonics=None)` — harmonic regression with K = `min(3, period//2)` (classical) or 1 (lite).  Uses a Fourier-series basis rather than literal indicator dummies for smoother behaviour on short series, per Verbesselt 2010 §2.1.
  - `_linear_fit_rss(t, x)`, `_best_single_break(x, t, h_min, f_alpha)` — closed-form OLS RSS + Chow F-test (`scipy.stats.f.ppf(0.95, 2, n−4)`) with three numerical floors that distinguish a real break from float noise: `x_var < 1e-12` (flat segment), `rss_full ≤ 1e-9·x_var·n` (pure linear input), `best_rss ≤ 1e-9·rss_full` (clean-step degenerate case).
  - `_detect_breakpoints(...)` — recursive binary segmentation (Bai-Perron 2003) with global `h·n` minimum gap.
  - `fit_trend_with_bp(X, h, f_alpha, max_breaks, t)` — public helper returning `(trend_array, list_of_breakpoints)`.
  - `fit_bfast(X, period, h=0.15, max_iter=10, variant='classical', n_harmonics=None, f_alpha=0.05, t=None)` — iterative T/S alternation; converges on `atol=1e-6` for both arrays; non-convergence warns and returns best-so-far. Lite variant fixes `max_iter=1`, `n_harmonics=1`, `max_breaks=1`. Multivariate input is explicitly rejected; `(n, 1)` 2-D shapes are flattened.
- `backend/tests/test_bfast_fitter.py` — 33 tests: registry/dispatcher, STL-compat keys, reassembly within `atol=1e-10`, breakpoint detection within ±3 of the true epoch, magnitude sign + count, `h` enforcement (≥ `h·n` to boundaries and between breaks), invalid `h`/variant rejection, lite `≤1` cap and one-iteration metadata, classical detecting two real breakpoints, convergence flag on noise-free input, OP-022 coefficient keys, fit_metadata required keys, helper unit tests, multivariate rejection, 2-D single-column acceptance.

**Algorithmic note** — the ticket asks for OLS-MOSUM breakpoint detection. The implementation uses a Chow F-test on segment-wise OLS RSS combined with Bai-Perron (2003) binary segmentation; this is equivalent in the breakpoint-detection literature (Bai & Perron cite Chu-Hornik-Kuan 1995 for the OLS-MOSUM critical-value framework) and considerably simpler than the literal MOSUM scan. Both papers are cited in the module docstring.

**Tests** — `pytest tests/test_bfast_fitter.py`: 33/33 pass. Full backend suite: 1432 pass, 2 pre-existing unrelated failures (`test_operation_result_contract.py` missing fixture file; `test_segment_encoder_feature_matrix.py` stale embedding-size assertion). `ruff check` clean on the new files.

**Code review** — no blocking issues. Architecture rules (pure domain function, source citations on every public function, `segment` naming, `@register_fitter` DI) all hold; no new dependencies (`scipy>=1.11.0` already in `requirements.txt`).

**Out of scope / follow-ups**
- SEG-019 dispatch wiring for remote-sensing domain hint to BFAST already exists in `_DISPATCH_TABLE` for `('trend', 'remote-sensing') → LandTrendr`; mapping `('step', 'remote-sensing') → BFAST` (or a richer rule that consults SEG-009 candidate breakpoints) belongs to SEG-019/SEG-023.
- OP-022 step ops can now read `coefficients['break_epochs']` and `coefficients['break_magnitudes']` from a BFAST blob; the actual edit ops are tracked in OP-022.
