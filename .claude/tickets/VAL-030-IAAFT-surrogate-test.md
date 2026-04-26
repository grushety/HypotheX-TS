# VAL-030 — IAAFT surrogate test (slow path)

**Status:** [ ] Done
**Depends on:** SEG-019 (decomposition blob), OP-050 (CF coordinator)

---

## Goal

Implement the **IAAFT (Iterative Amplitude-Adjusted Fourier Transform) surrogate test** as a slow-path validation invoked when the user clicks **"Run full validation"** on an edit. Generates B=500 surrogate series preserving the original power spectrum and amplitude distribution, then computes a discriminating statistic q(·) on the edited series and on each surrogate. Returns a permutation p-value answering: *"Is the edited series statistically distinguishable from natural variation that preserves the same nonlinear-equivalent structure?"*

**Why:** IAAFT is the canonical null-model surrogate for nonstationary nonlinear time series and the appropriate generator when KS/AD/MMD on residuals are insufficient (autocorrelation makes those tests over-reject). For long, high-stakes edits the user can spend 1–3 s for a calibrated p-value. **Critical companion to VAL-006 (ADF/KPSS) and VAL-008 (MMD)** — those are fast i.i.d. approximations; this is the rigorous null.

**How it fits:** Slow-path metric. Triggered explicitly by the user; cached per edit. Result surfaces as a dialog with p-value, statistic value, surrogate-distribution histogram, and (if rejection) a tip surfaced via VAL-020.

---

## Paper references (for `algorithm-auditor`)

- Schreiber & Schmitz, **"Surrogate time series,"** *Physica D* 142(3–4):346–382 (2000), DOI 10.1016/S0167-2789(00)00043-9 (canonical IAAFT algorithm).
- Theiler, Eubank, Longtin, Galdrikian, Farmer, **"Testing for nonlinearity in time series: the method of surrogate data,"** *Physica D* 58(1–4):77–94 (1992), DOI 10.1016/0167-2789(92)90102-S (foundational paper).
- Lancaster, Iatsenko, Pidde, Ticcinelli, Stefanovska, **"Surrogate data for hypothesis testing of physical systems,"** *Physics Reports* 748:1–60 (2018), DOI 10.1016/j.physrep.2018.06.001 (modern catalogue: FT, AAFT, IAAFT, twin, small-shuffle, pseudo-periodic, multivariate variants — algorithm-auditor reads §2.4 for IAAFT convergence criterion).
- Bandt & Pompe, **"Permutation entropy: a natural complexity measure for time series,"** *Phys. Rev. Lett.* 88:174102 (2002), DOI 10.1103/PhysRevLett.88.174102 (default discriminating statistic q(·)).

---

## Pseudocode

```python
# backend/app/services/validation/iaaft.py
import numpy as np
from typing import Callable

def iaaft_surrogate(x: np.ndarray, max_iter: int = 100, tol: float = 1e-6,
                    rng: np.random.Generator | None = None) -> np.ndarray:
    """One IAAFT surrogate per Schreiber & Schmitz 2000 Algorithm 1.

    Iteratively swaps amplitude and phase to preserve both the original
    power spectrum and the original amplitude distribution.
    """
    rng = rng or np.random.default_rng()
    n = len(x)
    sorted_x = np.sort(x)
    # Random initial permutation
    s = rng.permutation(x)
    amplitude_target = np.abs(np.fft.rfft(x))
    prev_diff = np.inf
    for _ in range(max_iter):
        # Step 1: enforce target spectrum
        S = np.fft.rfft(s)
        S = amplitude_target * np.exp(1j * np.angle(S))
        s_spec = np.fft.irfft(S, n=n)
        # Step 2: enforce target amplitude distribution (rank-replace)
        ranks = np.argsort(np.argsort(s_spec))
        s_new = sorted_x[ranks]
        diff = np.mean((s_new - s) ** 2)
        if abs(prev_diff - diff) < tol: break
        s = s_new; prev_diff = diff
    return s

def permutation_entropy(x: np.ndarray, m: int = 4, tau: int = 1) -> float:
    """Bandt-Pompe permutation entropy (default discriminating statistic)."""
    from itertools import permutations
    n = len(x)
    if n < m: return 0.0
    counts = {}
    for i in range(n - (m - 1) * tau):
        pattern = tuple(np.argsort(x[i : i + m * tau : tau]))
        counts[pattern] = counts.get(pattern, 0) + 1
    total = sum(counts.values())
    probs = np.array([c / total for c in counts.values()])
    return float(-np.sum(probs * np.log(probs)))

def iaaft_test(x_edit: np.ndarray, x_orig: np.ndarray,
               n_surrogates: int = 500,
               statistic: Callable[[np.ndarray], float] = permutation_entropy,
               n_jobs: int = -1, seed: int = 0) -> "IAAFTResult":
    """Two-sided IAAFT permutation test against the original series' null."""
    rng = np.random.default_rng(seed)
    q_edit = statistic(x_edit)
    seeds = rng.integers(0, 2**31, size=n_surrogates)
    surrogate_qs = parallel_map(
        lambda s: statistic(iaaft_surrogate(x_orig, rng=np.random.default_rng(s))),
        seeds, n_jobs=n_jobs,
    )
    surrogate_qs = np.array(surrogate_qs)
    # Two-sided p-value (Edgington-style permutation correction)
    p_two_sided = (1 + np.sum(np.abs(surrogate_qs - np.mean(surrogate_qs))
                              >= abs(q_edit - np.mean(surrogate_qs)))) / (n_surrogates + 1)
    return IAAFTResult(
        q_edit=q_edit,
        q_surrogate_mean=float(np.mean(surrogate_qs)),
        q_surrogate_std=float(np.std(surrogate_qs)),
        p_value=float(p_two_sided),
        surrogate_distribution=surrogate_qs,
        n_surrogates=n_surrogates,
        statistic_name=statistic.__name__,
    )
```

---

## Acceptance Criteria

- [ ] `backend/app/services/validation/iaaft.py` with `iaaft_surrogate`, `permutation_entropy`, `iaaft_test`, and `IAAFTResult` dataclass
- [ ] IAAFT algorithm matches Schreiber & Schmitz 2000 Algorithm 1: alternating spectrum-enforcement + rank-replace until tolerance reached
- [ ] Convergence test: surrogate's amplitude distribution is exactly the original's (rank-equivalent); surrogate's power spectrum matches original within configurable tolerance (default `||PSD_surr - PSD_orig||_∞ / ||PSD_orig||_∞ < 0.01`)
- [ ] Default statistic = permutation entropy (Bandt-Pompe 2002, m=4, τ=1); pluggable via `statistic` argument so users can pass correlation dimension or prediction error per Lancaster 2018 §3
- [ ] Two-sided permutation p-value uses Edgington-style correction `(1 + Σ ≥ obs) / (B + 1)` to avoid p=0
- [ ] Parallelised across surrogates via `joblib` with `n_jobs=-1`; B=500 on n=10⁴ completes in < 3 s on reference hardware (single CPU benchmark in CI)
- [ ] Result surfaced as a dialog: p-value, surrogate-distribution histogram, q_edit position; tip emitted via VAL-020 if `p < 0.05`
- [ ] Cached per-edit (key = hash of edit + n_surrogates + statistic name) to avoid re-running on tab switch
- [ ] **Methodological honesty:** docstring documents IAAFT's null hypothesis precisely (`H₀: x_edit is generated by a Gaussian linear process with the same amplitude distribution and power spectrum as x_orig`) — not "is plausible"
- [ ] `joblib` added to `backend/requirements.txt` (numpy/scipy already present)
- [ ] Tests cover: convergence on synthetic AR(1); permutation-entropy formula matches Bandt-Pompe paper Eq. 1 on hand-checked fixture; uniform white-noise surrogate has p ≈ 0.5 against itself; IAAFT-of-IAAFT preserves spectrum within tolerance; B=500 on n=10000 < 3 s
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "VAL-030: IAAFT surrogate test (slow-path)"` ← hook auto-moves this file to `done/` on commit
