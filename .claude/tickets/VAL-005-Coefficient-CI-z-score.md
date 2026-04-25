# VAL-005 — Coefficient-CI z-score (per-edit, fast path)

**Status:** [ ] Done
**Depends on:** SEG-013..018 (decomposition fitters), SEG-019 (blob)

---

## Goal

For each Tier-2 edit on a decomposition coefficient, compute the **z-score** of the edited value relative to the bootstrap CI of the original fit. Surfaces "how extreme is this edit relative to the model's own fitting uncertainty?"

**Why:** A user can confidently set `linear_rate = 0.5` after the fit produced `linear_rate = 0.51 ± 0.02`. That's a 1σ edit. But `linear_rate = 5.0` is a 200σ edit — almost certainly outside the data-generating process. The CI z-score quantifies this immediately and links the edit to the underlying model's epistemic uncertainty.

**How it fits:** Fast-path metric. CIs computed offline once per fit (cached). Per-edit cost: O(1) lookup + arithmetic. Wraps a uniform Politis–Romano stationary-bootstrap layer around all seven decompositions.

---

## Paper references (for `algorithm-auditor`)

- Politis & Romano, **"The Stationary Bootstrap,"** *JASA* 89:1303 (1994), DOI 10.1080/01621459.1994.10476870.
- Politis & White, **"Automatic Block-Length Selection,"** *Econometric Reviews* 23:53 (2004) (with Patton 2009 correction).
- Bergmeir, Hyndman, Benítez, **"Bagging exponential smoothing methods using STL decomposition and Box–Cox transformation,"** *Int. J. Forecasting* 32:303 (2016), DOI 10.1016/j.ijforecast.2015.07.002.
- Decomposition-specific:
  - ETM: Durbin & Koopman 2012 state-space SEs.
  - BFAST: Bai-Perron breakpoint CIs in `bfast::bfast01`.
  - LandTrendr: Kennedy et al. *Remote Sensing* 10:691 (2018).
  - Eckhardt: analytic sensitivity *HESS* 16:451 (2012).
  - GrAtSiD: external (CATS/Hector); Bedford & Bevis 2018.

---

## Pseudocode

```python
class CoefficientCIValidator:
    def __init__(self, blob: DecompositionBlob, B=500, block_length=None):
        self.blob = blob
        self.coeff_distributions = {}    # coefficient_name → np.ndarray of bootstrap samples
        self._compute_ci(B, block_length)

    def _compute_ci(self, B, block_length):
        """Offline: refit B times on stationary bootstrap resamples."""
        if block_length is None:
            block_length = politis_white_block_length(self.blob.residual)
        for b in range(B):
            X_resample = stationary_bootstrap(self.blob, block_length)
            blob_b = refit_same_method(self.blob.method, X_resample)
            for name, val in blob_b.coefficients.items():
                self.coeff_distributions.setdefault(name, []).append(val)
        # Convert to numpy
        self.coeff_distributions = {k: np.array(v) for k, v in self.coeff_distributions.items()}

    def z_score(self, coeff_name: str, edited_value: float) -> float:
        dist  = self.coeff_distributions[coeff_name]
        mean  = np.mean(dist)
        std   = np.std(dist)
        return (edited_value - mean) / max(std, 1e-12)

    def is_extreme(self, coeff_name, edited_value, threshold=3.0) -> bool:
        return abs(self.z_score(coeff_name, edited_value)) > threshold
```

---

## Acceptance Criteria

- [ ] `backend/app/services/validation/coefficient_ci.py` with:
  - `CoefficientCIValidator` class with `_compute_ci`, `z_score`, `is_extreme`
  - Per-blob CI computation (B=500 default; configurable `B` and `block_length`)
  - Block length auto-selected via Politis-White 2004 + Patton 2009 correction
- [ ] CIs cached on disk per (segment_id, blob_method); loaded lazily; recomputed on segment-boundary edit (OP-001) or split (OP-002)
- [ ] z-score > 3 triggers UI tip "edit modifies coefficient by ≫ its fitting uncertainty (extreme tampering)" (VAL-020)
- [ ] Per-edit lookup: O(1); precomputation: O(B · fit_cost) — runs in background after segment fit
- [ ] All seven decomposition methods supported (ETM/STL/MSTL/BFAST/LandTrendr/Eckhardt/GrAtSiD); methods with native CI (ETM, BFAST) fall back to stationary bootstrap if native CI unavailable
- [ ] Stored in `CFResult.validation.coefficient_ci`
- [ ] Tests: synthetic AR(1) — bootstrap CI on slope contains true value 95% of the time; z-score = 0 on identity edit; z-score > 3 on far edit; block-length selection deterministic
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper refs Politis & Romano 1994, Politis & White 2004, Bergmeir et al. 2016. Confirm: stationary bootstrap with geometric block lengths; block length matches Politis-White 2004 Eq. 3 with Patton 2009 correction; refit uses same method as original blob (no method substitution)
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "VAL-005: coefficient-CI z-score (per-edit fast path)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
