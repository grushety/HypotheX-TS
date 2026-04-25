# VAL-031 — Full moving-block bootstrap (slow path)

**Status:** [ ] Done
**Depends on:** SEG-013..018 (decomposition fitters); VAL-005 (uses cached B=500 CIs as fast-path; this slow path provides authoritative B=999)

---

## Goal

Implement the **full stationary moving-block bootstrap (MBB)** with B=999 replicates and **Politis-White (2004) automatic block-length selection** (with Patton-Politis-White 2009 correction). Provides authoritative confidence intervals on:

1. **Decomposition coefficients** (e.g. STL trend slope, MSTL seasonal amplitude, BFAST breakpoint magnitudes, GrAtSiD feature amplitudes)
2. **Aggregate metrics** computed by OP-033 (peak, area, BFI, period, τ, …)

**Why:** VAL-005 surfaces a fast-path z-score against a *pre-cached B=500* CI for the unedited series; this is acceptable for live feedback but is **not the published-paper-grade analysis**. The slow-path B=999 with optimal block-length is what reviewers will demand for publication-figure CIs.

**How it fits:** Slow-path metric. Triggered explicitly by the user; caches results per `(series_id, decomposition_method, coefficient_name)` keys. Provides the gold-standard CI used for comparing edit magnitude against natural sampling variability of the fit.

---

## Paper references (for `algorithm-auditor`)

- Politis & Romano, **"The Stationary Bootstrap,"** *JASA* 89(428):1303–1313 (1994), DOI 10.1080/01621459.1994.10476870.
- Politis & White, **"Automatic Block-Length Selection for the Dependent Bootstrap,"** *Econometric Reviews* 23(1):53–70 (2004), DOI 10.1081/ETC-120028836.
- Patton, Politis, White, **"Correction to 'Automatic Block-Length Selection for the Dependent Bootstrap',"** *Econometric Reviews* 28(4):372–375 (2009), DOI 10.1080/07474930802459016 (uses corrected formula — algorithm-auditor verifies the corrected one is implemented, not the 2004 original).
- Bergmeir, Hyndman, Benítez, **"Bagging exponential smoothing methods using STL decomposition and Box–Cox transformation,"** *International Journal of Forecasting* 32(2):303–312 (2016), DOI 10.1016/j.ijforecast.2015.07.002 (STL bootstrap protocol for residuals).
- Lahiri, **"Resampling Methods for Dependent Data,"** Springer 2003, ISBN 978-0-387-00928-1, Ch. 3 (overlapping vs. non-overlapping blocks; recommended block-length lower bounds).

---

## Pseudocode

```python
# backend/app/services/validation/mbb.py
from typing import Callable
from arch.bootstrap import StationaryBootstrap, optimal_block_length
import numpy as np

def politis_white_block_length(x: np.ndarray) -> int:
    """Optimal mean block length per Politis-White 2004 with Patton 2009 correction.
    Delegates to `arch.bootstrap.optimal_block_length` which implements the corrected formula."""
    result = optimal_block_length(x)
    # `arch` returns DataFrame with ['stationary', 'circular'] columns
    return int(np.ceil(result['stationary'].iloc[0]))

def mbb_ci(x: np.ndarray, statistic: Callable[[np.ndarray], float],
           n_replicates: int = 999, alpha: float = 0.05,
           block_length: int | None = None,
           seed: int = 0) -> "MBBResult":
    """Stationary block bootstrap CI for any scalar statistic of x.

    The block length is selected by Politis-White-Patton if not provided.
    """
    if block_length is None:
        block_length = politis_white_block_length(x)
    bs = StationaryBootstrap(block_length, x, seed=seed)
    point = statistic(x)
    bs_replicates = []
    for data in bs.bootstrap(n_replicates):
        bs_replicates.append(statistic(data[0][0]))
    bs_replicates = np.array(bs_replicates)
    lo, hi = np.quantile(bs_replicates, [alpha / 2, 1 - alpha / 2])
    return MBBResult(
        point_estimate=point,
        ci_lower=float(lo), ci_upper=float(hi),
        block_length=block_length,
        n_replicates=n_replicates,
        replicates=bs_replicates,
        statistic_name=statistic.__name__,
    )

def mbb_coefficient_ci(x: np.ndarray, decomposition_blob, coefficient_name: str,
                       refit_fn: Callable, n_replicates: int = 999,
                       seed: int = 0) -> "MBBResult":
    """CI for a decomposition coefficient: refit on each bootstrapped sample.

    Per Bergmeir-Hyndman-Benítez 2016: bootstrap is on the remainder/residual
    component, not the raw series, when a decomposition is available.
    """
    residual = decomposition_blob.components.get('residual') or \
               decomposition_blob.components.get('remainder')
    if residual is None:
        raise ValueError(f"blob method {decomposition_blob.method} has no residual component")
    block_length = politis_white_block_length(residual)
    bs = StationaryBootstrap(block_length, residual, seed=seed)
    fitted = []
    point = decomposition_blob.coefficients[coefficient_name]
    for data in bs.bootstrap(n_replicates):
        boot_residual = data[0][0]
        boot_series = (decomposition_blob.reassemble_without_residual()
                       + boot_residual)
        boot_blob = refit_fn(boot_series)
        fitted.append(boot_blob.coefficients[coefficient_name])
    fitted = np.array(fitted)
    lo, hi = np.quantile(fitted, [0.025, 0.975])
    return MBBResult(point_estimate=point, ci_lower=float(lo), ci_upper=float(hi),
                     block_length=block_length, n_replicates=n_replicates,
                     replicates=fitted, statistic_name=coefficient_name)
```

---

## Acceptance Criteria

- [ ] `backend/app/services/validation/mbb.py` with `politis_white_block_length`, `mbb_ci`, `mbb_coefficient_ci`, and `MBBResult` dataclass
- [ ] **Block length selection uses the Patton-Politis-White 2009 *corrected* formula**, not the 2004 original (delegates to `arch.bootstrap.optimal_block_length`); test asserts the value matches the `arch` reference for a known fixture
- [ ] Stationary block bootstrap (Politis-Romano 1994) used by default; configurable to circular/overlapping block bootstrap if user passes `bootstrap_type='circular'`
- [ ] **For decomposition coefficient CIs:** bootstrap is on the residual component (Bergmeir-Hyndman-Benítez 2016 protocol), refitting via `refit_fn`; raises informative error if blob has no residual component
- [ ] **For aggregate metrics (OP-033):** bootstrap is on the raw segment series; statistic re-applied per replicate
- [ ] B=999 default; user can override; B=999 on n=10⁴ completes in < 3 s for `mbb_ci`, < 30 s for `mbb_coefficient_ci` (depends on refit cost — flagged in result metadata)
- [ ] Result includes block length, n_replicates, statistic name, full replicate array (for histogram surfacing)
- [ ] Cached by `(series_id, statistic_name, n_replicates, seed)`
- [ ] Surfaced in slow-path dialog with histogram of replicates and 95 % CI bracket; user-edit value plotted as a vertical line
- [ ] **Methodological honesty:** docstring documents that MBB CI assumes weak stationarity *of the resampled component* — for a decomposition's residual this is reasonable; for the raw series under structural-break edits it is *not*, and the user should compare the result with the IAAFT (VAL-030) test in those cases. This caveat is also surfaced in the dialog footer
- [ ] `arch` (>=6.3) added to `backend/requirements.txt`
- [ ] Tests cover: `politis_white_block_length` matches arch reference on AR(1) fixture; `mbb_ci` recovers known mean CI on i.i.d. Gaussian within Monte-Carlo error; coverage of true mean ≥ 0.93 on 100 simulated datasets at α=0.05; coefficient CI bracket-width shrinks with B; reproducibility under seed
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper references: Politis-Romano 1994 Definition 2.1 (verify stationary-bootstrap geometric block-length distribution), Patton-Politis-White 2009 (verify *corrected* formula in use), Bergmeir-Hyndman-Benítez 2016 §2.2 (verify residual-bootstrap protocol). Cross-check against Lahiri 2003 Ch. 3 lower-bound recommendations on block length
- [ ] Run `code-reviewer` agent — no blocking issues; verify `arch` version pinned to one with the corrected block-length formula
- [ ] `git commit -m "VAL-031: full MBB B=999 with Politis-White-Patton block length (slow-path)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
