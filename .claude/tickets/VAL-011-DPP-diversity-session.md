# VAL-011 — DPP log-det diversity of accepted CFs (session-level)

**Status:** [ ] Done
**Depends on:** OP-041 (label chip events), VAL-003 (yNN index for embeddings)

---

## Goal

Compute the **DPP (Determinantal Point Process) log-det** of the set of accepted CFs in a session. High log-det = diverse exploration; low log-det = repeated similar CFs (cherry-picking signal).

**Why:** DiCE diversity (Mothilal FAccT 2020) used DPP at CF-generation time. Applying it at the *session* level lets the Guardrails sidebar surface "you've explored only one corner of the CF space." Adapted to TS via DTW kernel (no peer-reviewed standard yet — this is one of the open research gaps).

**How it fits:** Session-level metric. Updates incrementally as CFs are accepted. Adapts DiCE's DPP framework to TS by using a DTW or shapelet-distance kernel instead of Euclidean.

---

## Paper references (for `algorithm-auditor`)

- Mothilal, Sharma, Tan, **DiCE,** FAccT 2020, DOI 10.1145/3351095.3372850 (DPP definition for diversity).
- Russell, **"Efficient Search for Diverse Coherent Explanations,"** FAT* 2019, DOI 10.1145/3287560.3287569.
- Kulesza & Taskar, **"Determinantal Point Processes for Machine Learning,"** *Foundations and Trends in ML* 5:123 (2012) — DPP foundational reference.
- For TS-DTW kernel: no canonical paper; document this as project-specific extension.

---

## Pseudocode

```python
def dpp_log_det_diversity(cfs: list[CFResult], kernel: str = 'dtw_rbf'):
    """
    log det(K) where K_ij = k(c_i, c_j) — high = diverse.
    """
    n = len(cfs)
    if n < 2:
        return DiversityResult(log_det=float('-inf'), n_cfs=n, kernel=kernel)
    K = np.zeros((n, n))
    for i in range(n):
        for j in range(i, n):
            if kernel == 'dtw_rbf':
                d = dtw_distance(cfs[i].edited_series, cfs[j].edited_series)
                K[i, j] = K[j, i] = np.exp(-d ** 2 / (2 * SIGMA ** 2))
            elif kernel == 'shapelet_edit':
                d = shapelet_edit_distance(cfs[i], cfs[j])
                K[i, j] = K[j, i] = 1.0 / (1.0 + d)
            elif kernel == 'latent_euclidean':
                z_i, z_j = encoder(cfs[i]), encoder(cfs[j])
                K[i, j] = K[j, i] = np.exp(-np.sum((z_i - z_j) ** 2) / (2 * SIGMA ** 2))
    K += 1e-6 * np.eye(n)        # numerical regularisation
    sign, log_det = np.linalg.slogdet(K)
    return DiversityResult(log_det=float(log_det), n_cfs=n, kernel=kernel)
```

---

## Acceptance Criteria

- [ ] `backend/app/services/validation/diversity.py` with:
  - `DiversityResult` frozen dataclass: `log_det`, `n_cfs`, `kernel`
  - `dpp_log_det_diversity(cfs, kernel)` supporting `dtw_rbf` (default), `shapelet_edit`, `latent_euclidean`
  - Numerical regularisation `+1e-6 I` documented
- [ ] Incremental updates via Schur-complement formula (avoid full O(n³) recomputation per accept):
  - `log det(K_new) = log det(K_old) + log(K_nn − k^T K_old^{-1} k)` where `K_old^{-1}` is cached
- [ ] Kernel σ exposed in config; default = median DTW distance among accepted CFs (Gretton-style heuristic)
- [ ] Result surfaced in Guardrails sidebar (VAL-014)
- [ ] Low log-det relative to expected (calibrated per-dataset offline) triggers tip "all your CFs cluster in one region; try a contrasting primitive" (VAL-020)
- [ ] Latency: incremental update O(n²); full recompute on session start ≤ 1 s for n ≤ 100 accepted CFs
- [ ] Tests: identical CFs → log_det = -inf; orthogonal/diverse CFs → high log_det; incremental update agrees with full recompute within 1e-6
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper refs Mothilal 2020, Kulesza & Taskar 2012. Confirm: DPP definition matches Kulesza 2012 §2; kernel positivity guaranteed; numerical regularisation documented; Schur-complement incremental update is mathematically correct
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "VAL-011: DPP log-det diversity of accepted CFs (session-level)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
