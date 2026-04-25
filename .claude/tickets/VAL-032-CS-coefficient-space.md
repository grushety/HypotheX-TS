# VAL-032 — Counterfactual Stability for decomposition coefficient space

**Status:** [ ] Done — **PUBLISHABLE CONTRIBUTION**
**Depends on:** SEG-019 (decomposition blob), OP-050 (CF coordinator), VAL-031 (per-coefficient SEs from MBB used to calibrate the noise model)

---

## Goal

**Transplant Counterfactual Stability (Dutta et al. ICML 2022) from the tabular setting to the decomposition-coefficient space of fitted parametric time-series models.** Given a CF produced by OP-050 in the form of edited coefficients `θ' = θ + Δθ`, sample M=200 perturbations of `θ'` from a Gaussian centred at `θ'` with covariance `Σ_θ` calibrated from the per-coefficient SEs (VAL-031), reassemble each perturbed series, query the model, and return:

```
CS(θ') = μ_M − κ σ_M,         κ = 0.5 (Dutta 2022 default)
```

where `μ_M` and `σ_M` are the mean and SD of the model's predicted-class probability (or distance-to-decision-boundary for regression) across the M samples.

**Why publishable:** Per the [[HypotheX-TS - Statistical Validation SOTA]] review, no work in 2020–2026 has transplanted CS / TRex / PROBE to time-series counterfactuals operating in **fitted-parametric-decomposition coefficient space**. Choosing the temporal noise model (per-coefficient Gaussian calibrated to MBB SEs) and proving probabilistic validity bounds is a clean ICML / NeurIPS / ECAI contribution. **This is contribution #1 from §"Open research gaps"** of the SOTA review.

**How it fits:** Slow-path (M=200 model queries take ≈ 1–3 s for typical models). Triggered explicitly by the user's "Run full validation" button or by VAL-020 escalating after the fast-path PROBE-IR (VAL-002) crosses a high threshold.

---

## Paper references (for `algorithm-auditor`)

- Dutta, Long, Mishra, Tilli, Magazzeni, **"Robust Counterfactual Explanations for Tree-Based Ensembles,"** *ICML 2022* (PMLR 162:5742–5756), arXiv 2207.02739 (canonical CS definition; algorithm-auditor reads §3 for the CS = μ − κσ formula and §4 for choice of κ).
- Hamman, Noorani, Mishra, Magazzeni, Dutta, **"Robust Counterfactual Explanations for Neural Networks With Probabilistic Guarantees,"** *ICML 2023* (PMLR 202:12351), arXiv 2305.11997 (companion bound for differentiable models — used here for the optional analytic-bound variant).
- Pawelczyk, Datta, van-den-Heuvel, Kasneci, Lakkaraju, **"Probabilistically Robust Recourse,"** *ICLR 2023*, arXiv 2203.06768 (PROBE-IR — the fast-path companion in VAL-002; this slow-path is the calibrated MC version).
- Mishra, Dutta, Long, Magazzeni, **"A Survey on the Robustness of Feature Importance and Counterfactual Explanations,"** arXiv 2111.00358 (2021) (overview).
- Slack, Hilgard, Lakkaraju, Singh, **"Counterfactual Explanations Can Be Manipulated,"** *NeurIPS 2021*, arXiv 2106.02666 (motivating threat model).

For the **MBB-calibrated noise model** (the publishable novel piece): Politis & Romano 1994; Patton-Politis-White 2009 (cited in VAL-031); Bedford & Bevis *JGR Solid Earth* 123:6992 (2018) DOI 10.1029/2017JB014765 (per-feature SE protocol for transient-decomposition coefficients).

---

## Pseudocode

```python
# backend/app/services/validation/cs_coefficient.py
import numpy as np
from dataclasses import dataclass

@dataclass(frozen=True)
class CSResult:
    cs: float                              # CS = μ − κσ (Dutta 2022 Def. 1)
    mu: float                              # μ_M
    sigma: float                           # σ_M
    invalidation_rate: float               # fraction of M samples that flip prediction
    n_samples: int
    sigma_theta: dict[str, float]          # per-coefficient SE used for the noise model
    is_robust: bool                        # CS > τ_robust (default 0.5)

def cs_coefficient_space(
    blob,                                  # DecompositionBlob (edited)
    target_class,                          # the CF target class
    model_predict_proba,                   # callable: (n,) → P(class)
    sigma_theta: dict[str, float],         # per-coefficient SE from VAL-031 MBB
    n_samples: int = 200,
    kappa: float = 0.5,
    seed: int = 0,
) -> CSResult:
    """CS in coefficient space per Dutta 2022 §3, transplanted to TS decompositions.

    Noise model: θ_m = θ' + ε_m,  ε_m ~ N(0, diag(σ_θ²))   for m = 1..M
    """
    rng = np.random.default_rng(seed)
    edited_coeffs = dict(blob.coefficients)
    coeff_names = list(edited_coeffs.keys())
    sigma_vec = np.array([sigma_theta.get(n, 0.0) for n in coeff_names])
    samples_proba = []
    n_invalid = 0
    base_pred = np.argmax(model_predict_proba(blob.reassemble()))
    for _ in range(n_samples):
        eps = rng.normal(0.0, sigma_vec)
        perturbed = {n: edited_coeffs[n] + e for n, e in zip(coeff_names, eps)}
        perturbed_blob = blob.with_coefficients(perturbed)        # immutable replace
        x_m = perturbed_blob.reassemble()
        proba = model_predict_proba(x_m)
        samples_proba.append(proba[target_class])
        if np.argmax(proba) != base_pred:
            n_invalid += 1
    samples_proba = np.array(samples_proba)
    mu = float(np.mean(samples_proba)); sigma = float(np.std(samples_proba))
    cs = mu - kappa * sigma
    return CSResult(
        cs=cs, mu=mu, sigma=sigma,
        invalidation_rate=n_invalid / n_samples,
        n_samples=n_samples,
        sigma_theta=sigma_theta,
        is_robust=cs > 0.5,
    )
```

---

## Acceptance Criteria

- [ ] `backend/app/services/validation/cs_coefficient.py` with `CSResult` dataclass and `cs_coefficient_space`
- [ ] **CS formula matches Dutta 2022 Def. 1 exactly** — `CS = μ − κσ` with default `κ = 0.5`; algorithm-auditor verifies against paper
- [ ] **Noise model is calibrated to per-coefficient MBB SEs (VAL-031)** — not arbitrary Gaussian σ. Pulls `σ_theta` for each coefficient from VAL-031 cache; raises informative error if VAL-031 has not been run for the segment
- [ ] **Coefficient-space-only:** the function never perturbs raw signal values directly; perturbations are applied to the coefficient dict and the series is reassembled. Asserted by a grep test in CI
- [ ] Each perturbed sample reassembled via `blob.with_coefficients(perturbed).reassemble()`; `with_coefficients` returns a deep copy (immutability test)
- [ ] **Returns invalidation rate alongside CS** — the proportion of M samples whose argmax-class differs from the unperturbed CF; this is the slow-path counterpart to VAL-002 PROBE-IR
- [ ] M=200 default; tunable; M=200 with model-predict cost ≤ 10 ms completes in < 3 s; M=200 with cost up to 50 ms shows progress bar
- [ ] Cache key = `(blob_hash, target_class, M, kappa, seed)`
- [ ] **Methodological honesty:** docstring explicitly states this is a transplant of CS to TS decomposition spaces, lists assumptions (Gaussian per-coefficient noise, independence across coefficients), and notes the *alternative* MMD-coupled noise model is left for follow-up. Includes a paper-draft TODO comment listing the publishable claim
- [ ] **Optional Hamman-2023 analytic bound:** when the model is differentiable (e.g. has a `gradient` method), expose `cs_analytic_bound(blob, target_class, model)` returning the Hamman 2023 closed-form lower bound on Pr(robust). Off by default; gated behind `analytic_bound=True`
- [ ] Result surfaces in slow-path dialog with: CS value, μ ± σ, invalidation rate %, histogram of M proba samples; tip emitted via VAL-020 if `cs < 0.5` ("edit is fragile") or `is_robust = False`
- [ ] Tests cover: CS formula on synthetic deterministic case (σ=0 → CS=μ); reproducibility under seed; coefficient-space-only invariant; raises if VAL-031 cache missing; M=200 latency on small fixture; analytic bound returns ≤ MC-CS for piecewise-linear toy model
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper references: Dutta 2022 §3 Def. 1 (CS formula), §4.2 (κ choice), Hamman 2023 §3 (analytic bound, if implemented), Pawelczyk 2023 (PROBE comparison). Confirm:
  - CS = μ − κσ (NOT μ + κσ — sign error would invalidate the metric)
  - Invalidation rate is the proportion that flips prediction (NOT 1 − validity)
  - Per-coefficient noise model is calibrated, documented, and not arbitrary
  - The TS-coefficient-space transplant is correctly flagged as a publishable extension with explicit assumptions listed
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "VAL-032: CS in decomposition coefficient space (publishable transplant of Dutta 2022)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
