# VAL-002 — PROBE invalidation rate (linearised, per-edit)

**Status:** [ ] Done
**Depends on:** OP-050 (CF coordinator), differentiable forecaster

---

## Goal

Compute the **invalidation rate** `IR(x') = E_σ[M(x' + σ) ≠ M(x')]` for each committed edit using Pawelczyk et al.'s closed-form first-order linearised bound (PROBE, ICLR 2023). IR answers: "what fraction of imperfect realisations of this edit would the model invalidate?"

**Why:** A user committing a CF edit produces an *intent*, but the actual implementation drifts (parameter jitter, time-axis ambiguity, rounding). PROBE-IR quantifies how much that drift could change the model's verdict. This is the closest-fitting robustness metric to HypotheX-TS's actual workflow.

**How it fits:** Fast-path metric. Runs after OP-050 for every edit. Linearised analytic form (O(d)) fits the 200 ms budget; Monte-Carlo fallback only on user request via the slow-path panel.

---

## Paper references (for `algorithm-auditor`)

- Pawelczyk, Datta, van-den-Heuvel, Kasneci, Lakkaraju, **"Probabilistically Robust Recourse,"** ICLR 2023, arXiv 2203.06768.
- GitHub reference: `MartinPawelczyk/ProbabilisticallyRobustRecourse`.

---

## Pseudocode

```python
def probe_invalidation_rate(model, x_prime, sigma=0.1, method='linearised'):
    """
    Returns IR ∈ [0, 1]: probability M(x' + ε) ≠ M(x'), ε ~ N(0, σ² I).
    """
    if method == 'linearised':
        # First-order Taylor expansion (Pawelczyk Eq. 5)
        grad = model.gradient(x_prime)                       # ∇f(x')
        f0   = model.predict(x_prime)
        # Margin to decision boundary
        margin = abs(f0 - model.threshold)
        # Variance of f(x' + ε) ≈ σ² ‖∇f‖²
        std_f  = sigma * np.linalg.norm(grad)
        # P(|f - f0| > margin) under Gaussian approx
        return 2 * (1 - Phi(margin / max(std_f, 1e-12)))
    elif method == 'monte_carlo':
        N = 200
        eps = sigma * np.random.randn(N, len(x_prime))
        flips = sum(model.predict(x_prime + e) != model.predict(x_prime) for e in eps)
        return flips / N
```

---

## Acceptance Criteria

- [ ] `backend/app/services/validation/probe_ir.py` with:
  - `probe_invalidation_rate(model, x_prime, sigma, method='linearised') -> float`
  - Method `'linearised'` (default; ≤ 50 ms via single backward pass)
  - Method `'monte_carlo'` (slow-path; N=200 default)
- [ ] σ exposed in config; default σ = 0.1 in standardised feature space; HypotheX-TS uses domain-specific σ per Tier-2 op (e.g. amplitude ops: σ on coefficient; time ops: σ on shift)
- [ ] `IR > 0.2` triggers UI tip "edit may be invalidated by ~X% of imperfect realisations" (VAL-020 rule)
- [ ] Linearised path requires the model to expose `model.gradient(x)`; documented contract; non-differentiable models fall back to Monte Carlo
- [ ] Output stored in `CFResult.validation.probe_ir`
- [ ] Tests: linearised vs Monte-Carlo agree within 0.05 on synthetic logistic model; σ sensitivity (larger σ → larger IR); piecewise-linear bound matches Pawelczyk 2023 Eq. 5 closed form
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "VAL-002: PROBE invalidation rate (linearised per-edit)"` ← hook auto-moves this file to `done/` on commit
