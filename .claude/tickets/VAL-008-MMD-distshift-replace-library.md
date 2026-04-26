# VAL-008 — Linear-time MMD on residuals (for replace_from_library)

**Status:** [ ] Done
**Depends on:** OP-012 (replace_from_library)

---

## Goal

For each Tier-1 `replace_from_library` op, compute the **linear-time MMD estimator** between the donor-replaced window and its surrounding context (or a held-out reference distribution from the original series). Detects whether the donor introduces distributional shift relative to the rest of the series.

**Why:** Donor-based CFs (Native Guide, SETS, Discord, TimeGAN) can produce technically valid CFs that are stylistically off from the rest of the user's series — wrong noise level, wrong amplitude scale, wrong harmonic content. MMD on whitened residuals catches this without parametric assumptions. Linear-time estimator (Gretton et al. JMLR 2012, Theorem 6) keeps the test in the 200 ms budget.

**How it fits:** Edit-type-specific metric for OP-012. Runs after donor crossfade. Result feeds UI plausibility badge (UI-012) and tip engine (VAL-020).

---

## Paper references (for `algorithm-auditor`)

- Gretton, Borgwardt, Rasch, Schölkopf, Smola, **"A Kernel Two-Sample Test,"** *JMLR* 13:723 (2012). Theorem 6 = linear-time MMD².
- Lloyd, Ghahramani, **"Statistical Model Criticism using Kernel Two Sample Tests,"** NeurIPS 2015 (block-permutation null calibration).

---

## Pseudocode

```python
def mmd_linear_time(X, Y, kernel='rbf_median'):
    """
    Linear-time MMD² estimator (Gretton 2012 Theorem 6).
    Operates on N pairs of (X, Y) samples, O(N) cost vs O(N²) for quadratic.
    """
    assert len(X) == len(Y), "linear MMD requires equal-length samples"
    N = len(X) // 2

    if kernel == 'rbf_median':
        sigma = np.median(np.linalg.norm(X[:, None] - X[None, :], axis=-1))
        k = lambda u, v: np.exp(-np.linalg.norm(u - v) ** 2 / (2 * sigma ** 2))

    h = [
        k(X[2*i],     X[2*i+1])
        + k(Y[2*i],   Y[2*i+1])
        - k(X[2*i],   Y[2*i+1])
        - k(X[2*i+1], Y[2*i])
        for i in range(N)
    ]
    mmd2 = np.mean(h)
    var  = np.var(h) / N
    return MMDLinearResult(mmd2=mmd2, std_err=np.sqrt(var),
                           z_score=mmd2 / np.sqrt(max(var, 1e-12)))

def replace_library_distshift(window_post, context, n_permutations=200):
    """Block-permutation null calibration."""
    actual = mmd_linear_time(window_post, context)
    perm_distribution = []
    for _ in range(n_permutations):
        combined = np.concatenate([window_post, context])
        # Stationary block permutation preserving autocorrelation
        block_len = politis_white_block_length(combined)
        permuted = stationary_bootstrap(combined, block_len)
        a, b = permuted[:len(window_post)], permuted[len(window_post):]
        perm_distribution.append(mmd_linear_time(a, b).mmd2)
    p_value = np.mean([p >= actual.mmd2 for p in perm_distribution])
    return DistShiftResult(mmd2=actual.mmd2, std_err=actual.std_err,
                           z_score=actual.z_score, p_value=p_value)
```

---

## Acceptance Criteria

- [ ] `backend/app/services/validation/mmd_distshift.py` with:
  - `MMDLinearResult` and `DistShiftResult` frozen dataclasses
  - `mmd_linear_time(X, Y, kernel='rbf_median')` linear-time estimator (Gretton 2012 Th. 6)
  - `replace_library_distshift(window_post, context, n_permutations=200)` block-permutation calibration
  - Operates on **whitened residuals**, not raw series — guardrail enforced (asserts whitening upstream)
- [ ] Median-heuristic σ computed from concatenated sample (not just X)
- [ ] Block-permutation null preserves autocorrelation via stationary bootstrap (Politis-Romano 1994)
- [ ] p < 0.05 triggers UI tip "donor introduces distributional shift; try a different backend or smaller crossfade" (VAL-020)
- [ ] Linear-time path: ≤ 30 ms at n = 10k; full permutation calibration: ≤ 1 s with B=200
- [ ] OP-012 calls this after crossfade; result attached to `CFResult.validation.mmd_distshift`
- [ ] Tests: same-distribution (X, Y both N(0,1)) — p > 0.1; different-distribution (X N(0,1), Y N(1,1)) — p < 0.05; autocorrelated nulls correctly calibrated (no false positives on AR(1) data); linear vs quadratic MMD agree within 0.05 on small samples
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "VAL-008: linear-time MMD distributional shift (replace_from_library)"` ← hook auto-moves this file to `done/` on commit
