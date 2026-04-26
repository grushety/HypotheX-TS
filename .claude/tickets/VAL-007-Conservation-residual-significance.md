# VAL-007 — Conservation-residual significance (for enforce_conservation)

**Status:** [ ] Done
**Depends on:** OP-032 (enforce_conservation), OP-051 (compensation projection)

---

## Goal

For each Tier-3 `enforce_conservation` op, attach a confidence interval and p-value to the conservation residual. Three tests run jointly:

1. **Bootstrap CI on mean conservation residual** `r_t = Σ fluxes − dStorage/dt` with H₀: E[r] = 0
2. **Ratio statistic** `‖r_post‖² / ‖r_pre‖²` with F-like reference
3. **MMD** between `r_pre` and `r_post` distributions

**Why:** Patil et al. (arXiv 2601.08999, 2026) introduced physics-guided CFs but did **not** attach formal p-values to conservation residuals. HypotheX-TS adding bootstrap CI publishes a "conservation tightness" badge that fills this gap — directly publishable as a methodological contribution.

**How it fits:** Edit-type-specific metric for OP-032. Runs after compensation projection (OP-051). Result populates UI-010 constraint-budget bar with statistical confidence.

---

## Paper references (for `algorithm-auditor`)

- Beucler, Pritchard, Rasp, Ott, Baldi, Gentine, **"Enforcing Analytic Constraints in Neural Networks Emulating Physical Systems,"** *Phys. Rev. Lett.* 126:098302 (2021), DOI 10.1103/PhysRevLett.126.098302.
- Patil, Ji, Aydin, **"Physics-Guided Counterfactual Explanations for Large-Scale Multivariate Time Series,"** arXiv 2601.08999 (Jan 2026).
- Politis & Romano, **"The Stationary Bootstrap,"** *JASA* 89:1303 (1994).
- Gretton, Borgwardt, Rasch, Schölkopf, Smola, **"A Kernel Two-Sample Test,"** *JMLR* 13:723 (2012) — MMD.

---

## Pseudocode

```python
def conservation_residual_ci(r, B=999, block_length=None) -> ConservationCIResult:
    """Stationary block bootstrap CI for E[r] = 0 hypothesis."""
    if block_length is None:
        block_length = politis_white_block_length(r)
    means = [np.mean(stationary_bootstrap(r, block_length)) for _ in range(B)]
    ci_lo, ci_hi = np.quantile(means, [0.025, 0.975])
    p_value = 2 * min(np.mean([m >= 0 for m in means]),
                      np.mean([m <= 0 for m in means]))
    return ConservationCIResult(mean=np.mean(r), ci=(ci_lo, ci_hi), p_value=p_value)

def conservation_ratio_test(r_pre, r_post) -> RatioTestResult:
    norm_sq_pre  = np.sum(r_pre  ** 2)
    norm_sq_post = np.sum(r_post ** 2)
    ratio = norm_sq_post / max(norm_sq_pre, 1e-12)
    # Wilson-style CI under approximate F-reference
    F = ratio * (len(r_pre) - 1) / (len(r_post) - 1)
    p_value = 1 - scipy.stats.f.cdf(F, len(r_post) - 1, len(r_pre) - 1)
    return RatioTestResult(ratio=ratio, p_value=p_value)

def conservation_mmd_test(r_pre, r_post) -> MMDResult:
    from sklearn.metrics import pairwise_distances
    sigma = np.median(pairwise_distances(r_pre.reshape(-1, 1)))
    K_pp = rbf_kernel(r_pre,  r_pre,  sigma)
    K_qq = rbf_kernel(r_post, r_post, sigma)
    K_pq = rbf_kernel(r_pre,  r_post, sigma)
    mmd2 = np.mean(K_pp) + np.mean(K_qq) - 2 * np.mean(K_pq)
    p_value = permutation_test_mmd(r_pre, r_post, mmd2, B=200)
    return MMDResult(mmd2=mmd2, p_value=p_value)

def conservation_significance(r_pre, r_post) -> ConservationSignificance:
    return ConservationSignificance(
        residual_ci_post=conservation_residual_ci(r_post),
        ratio_test=conservation_ratio_test(r_pre, r_post),
        mmd_test=conservation_mmd_test(r_pre, r_post),
    )
```

---

## Acceptance Criteria

- [ ] `backend/app/services/validation/conservation_significance.py` with three test functions and a top-level `conservation_significance(r_pre, r_post)` orchestrator
- [ ] `ConservationCIResult`, `RatioTestResult`, `MMDResult` frozen dataclasses with named fields
- [ ] B=999 default for bootstrap; configurable via `ConservationConfig`
- [ ] MMD permutation null calibration with B=200 permutations (linear-time bound)
- [ ] All three tests use the *same* residual definition (Σ fluxes − dStorage/dt) consistent with OP-032
- [ ] Result populates UI-010 budget-bar tooltip: "Residual mean = X (95% CI [a, b]); ratio test p = Y; MMD p = Z"
- [ ] Latency: bootstrap + ratio ≤ 200 ms at n ≤ 10k; MMD ≤ 1 s with B=200 permutations (slow-path acceptable)
- [ ] Stored in `CFResult.validation.conservation` for OP-032 calls
- [ ] Tests: synthetic conservation-satisfying r → CI contains 0 and p > 0.05; synthetic r with bias → CI excludes 0 and p < 0.05; ratio test reduces correctly when residual is halved; MMD detects distributional shift on shifted residuals
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "VAL-007: conservation-residual significance for enforce_conservation"` ← hook auto-moves this file to `done/` on commit
