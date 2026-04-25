# VAL-006 — ADF + KPSS joint stationarity tests (per-edit, fast path)

**Status:** [ ] Done
**Depends on:** OP-050, decomposition residual access

---

## Goal

Run **ADF and KPSS jointly** (with opposite null hypotheses) on whitened residuals before and after each edit. Detects whether the manipulation introduced spurious non-stationarity (drift, level shift) that the user did not intend.

**Why:** A user editing a single segment may inadvertently introduce a unit root or break stationarity at the segment boundary. ADF tests H₀: unit root present; KPSS tests H₀: trend-stationary. Running both jointly avoids the well-known asymmetric failure mode of either test alone. Zivot-Andrews is added for one-break robustness on suppress/scale ops.

**How it fits:** Fast-path metric. Tests run on whitened residual time series. Cost O(n)–O(n log n), <10 ms per test, well within 200 ms budget.

---

## Paper references (for `algorithm-auditor`)

- Dickey & Fuller (1979/1981) — ADF test, *JASA* 74:427.
- Kwiatkowski, Phillips, Schmidt, Shin, **"Testing the null hypothesis of stationarity against the alternative of a unit root,"** *J. Econometrics* 54:159 (1992), DOI 10.1016/0304-4076(92)90104-Y.
- Phillips & Perron, *Biometrika* 75:335 (1988) — PP test (alternative).
- Zivot & Andrews, *J. Business & Economic Statistics* 10:251 (1992) — one-break unit-root test.
- Library: `statsmodels.tsa.stattools.adfuller`, `kpss`, `zivot_andrews`.

---

## Pseudocode

```python
def whiten_residual(r, ar_order='auto'):
    """Pre-whiten residual via AR fit before stationarity testing."""
    from statsmodels.tsa.ar_model import AutoReg
    if ar_order == 'auto':
        ar_order = min(int(np.cbrt(len(r))), 10)
    ar_fit = AutoReg(r, lags=ar_order).fit()
    return ar_fit.resid

def joint_stationarity_check(x_pre, x_post) -> StationarityResult:
    from statsmodels.tsa.stattools import adfuller, kpss, zivot_andrews
    r_pre  = whiten_residual(x_pre  - fitted_trend(x_pre))
    r_post = whiten_residual(x_post - fitted_trend(x_post))

    adf_pre   = adfuller(r_pre)[1]                 # p-value
    adf_post  = adfuller(r_post)[1]
    kpss_pre  = kpss(r_pre, regression='c')[1]
    kpss_post = kpss(r_post, regression='c')[1]
    za_post   = zivot_andrews(x_post)              # one-break, on RAW post (not residual)

    return StationarityResult(
        adf_pre_p=adf_pre, adf_post_p=adf_post,
        kpss_pre_p=kpss_pre, kpss_post_p=kpss_post,
        za_post_break=za_post.break_date if za_post.pvalue < 0.05 else None,
        verdict=_classify(adf_pre, adf_post, kpss_pre, kpss_post),
    )

def _classify(adf_pre, adf_post, kpss_pre, kpss_post, alpha=0.05):
    pre_stationary  = adf_pre  < alpha and kpss_pre  > alpha
    post_stationary = adf_post < alpha and kpss_post > alpha
    if pre_stationary and not post_stationary:
        return 'edit_introduced_nonstationarity'
    if not pre_stationary and post_stationary:
        return 'edit_reduced_nonstationarity'
    if pre_stationary and post_stationary:
        return 'stationary_preserved'
    return 'nonstationary_preserved'
```

---

## Acceptance Criteria

- [ ] `backend/app/services/validation/stationarity.py` with:
  - `StationarityResult` frozen dataclass: ADF/KPSS p-values pre+post, ZA break-date (None if no break), verdict ∈ {'edit_introduced_nonstationarity', 'edit_reduced_nonstationarity', 'stationary_preserved', 'nonstationary_preserved'}
  - `joint_stationarity_check(x_pre, x_post) -> StationarityResult`
  - `whiten_residual(r, ar_order='auto')` helper
- [ ] Whitening order auto-selected (cube-root rule, capped at 10) or user-specified
- [ ] α exposed; default α=0.05
- [ ] `verdict='edit_introduced_nonstationarity'` triggers UI tip "edit appears to have introduced non-stationary drift" (VAL-020)
- [ ] If Z-A break-date inconsistent with edit window (>20% of edit-window length away), trigger tip "manipulation introduced unintended break at t=…; tighten edit boundaries"
- [ ] Latency: ≤ 30 ms total for ADF + KPSS + ZA on n ≤ 10k samples
- [ ] Stored in `CFResult.validation.stationarity`
- [ ] Tests: synthetic stationary AR(1) — both tests agree; synthetic random walk — ADF rejects no, KPSS rejects yes; mid-stream level shift — ZA detects break
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper refs Dickey-Fuller 1979, KPSS 1992, Zivot-Andrews 1992. Confirm: tests run on whitened residual not raw series; ADF lag order matches Schwert 1989 default; KPSS regression term ('c' constant, 'ct' constant+trend) configurable; ZA on raw post-edit series (not residual) per paper convention
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "VAL-006: ADF + KPSS joint stationarity tests (per-edit)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
