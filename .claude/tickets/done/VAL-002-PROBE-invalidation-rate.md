# VAL-002 — PROBE invalidation rate (linearised, per-edit)

**Status:** [x] Done
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

- [x] `backend/app/services/validation/probe_ir.py` with:
  - `probe_invalidation_rate(model, x_prime, sigma, method='linearised') -> ProbeIRResult`
  - Method `'linearised'` (default; closed-form, single forward + backward, well under 50 ms)
  - Method `'monte_carlo'` (slow-path; N=200 default)
- [x] σ exposed in config; default σ = 0.1 in standardised feature space; HypotheX-TS uses domain-specific σ per Tier-2 op via `TIER2_DEFAULT_SIGMA` (amplitude ops: σ on coefficient ≈ 0.05; time ops: σ on shift ≈ 0.5)
- [x] `IR > 0.2` triggers UI tip "edit may be invalidated by ~X% of imperfect realisations" (VAL-020 rule) — *value plumbed into `CFResult.validation.probe_ir`; UI rule lands in VAL-020*
- [x] Linearised path requires the model to expose `model.gradient(x)`; documented contract; non-differentiable models fall back to Monte Carlo (raises `ProbeMethodError` if `linearised` requested without `gradient`)
- [x] Output stored in `CFResult.validation.probe_ir`
- [x] Tests: linearised vs Monte-Carlo agree within 0.05 on synthetic logistic model; σ sensitivity (larger σ → larger IR); piecewise-linear bound matches Pawelczyk 2023 Eq. 5 closed form
- [x] `pytest backend/tests/` passes (3 pre-existing unrelated failures excluded; see Result Report)

## Result Report

**Implementation summary.** Added `backend/app/services/validation/probe_ir.py` with `probe_invalidation_rate(model, x_prime, *, sigma, method, n_samples, rng) -> ProbeIRResult`, `ProbeModel` Protocol (`score`, `gradient`, `predict`, `threshold`), `ProbeIRResult` frozen dataclass, `ProbeMethodError`, and a `TIER2_DEFAULT_SIGMA` map plus `default_sigma_for_op` helper. Wired into `synthesize_counterfactual` via three optional kwargs (`probe_model`, `probe_sigma`, `probe_method`); when `probe_model` is supplied, IR is computed on `X_edit` and attached to the new `ValidationResult.probe_ir` field (forward-string annotation to avoid a circular import — runtime type is `ProbeIRResult | None`). `probe_sigma=None` falls back to the per-op default.

**Pseudocode-vs-paper deviation (load-bearing, same shape as VAL-001).** The ticket pseudocode shows `2 · (1 − Φ(margin/std_f))`, which is a two-sided test (probability of any deviation past the margin in either direction). A binary prediction can only flip in one direction for a fixed `x'`, so the factor of 2 is incorrect for `IR(x')`. Pawelczyk 2023 Eq. 5 — which the AC binds correctness to — is the one-sided closed form `IR ≈ 1 − Φ(margin / (σ · ‖∇f‖))`. The implementation follows the paper; deviation is documented in the module docstring.

**Numerical stability.** Closed form uses `0.5 · erfc(z/√2)` rather than `1 − Φ(z)`; the latter underflows in the deep tail once `erf(z/√2)` saturates near 1, breaking the σ-monotonicity test (caught by `test_ir_monotonic_in_sigma` at σ=0.05). `erfc` retains precision out to z ≈ 25.

**Gradient-shape guard.** A wrong-length `model.gradient(x)` (different element count than `x`) is the most insidious failure mode for a robustness metric — silently flattening would produce a meaningless IR. The validator raises `ProbeMethodError` instead.

**Tests.** 23 new tests in `test_probe_ir.py`: closed-form vs Eq. 5 (margin=0 → IR=0.5; margin/std_f=1 → IR≈0.1587; far-from-boundary → ~0); linearised vs MC agreement within 0.05 at margin/std_f=1 and far-from-boundary; σ monotonicity across [0.05, 2.0]; σ→∞ → IR→0.5; non-differentiable model raises on linearised; MC works on indicator model; method-string validation; IR ∈ [0,1] DTO guard; gradient-shape mismatch guard; default-σ-per-op map; OP-050 wiring (probe_model present/absent, σ falls back to op map).

**Test results.** `test_probe_ir.py`: 23/23. `test_conformal_pid.py`: 26/26. `test_cf_coordinator.py`: 37/37 (no regressions from new validation kwargs / new field on `ValidationResult`). Frontend: 645/645. Pre-existing unrelated failures untouched (`test_segmentation_eval.py` collection error from `LlmSegmentLabelerConfig` rename; `test_operation_result_contract.py` missing fixture file; `test_segment_encoder_feature_matrix.py` embedding-size drift) — all known-broken on `main` before this ticket.

**Code review.** APPROVE, 0 blocking. Two correctness wins addressed inline: gradient-shape mismatch now raises `ProbeMethodError` (was silent flatten); moved `default_sigma_for_op` import to module top (was per-call). Other NITs (helper to deduplicate `ProbeMethodError` message; `ProbeIRResult` triplicate `# type: ignore` comments; externalising `TIER2_DEFAULT_SIGMA` to `mvp-domain-config.json`) deferred — none are contract violations and the σ-map externalisation is a separate config-shaped ticket.

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "VAL-002: PROBE invalidation rate (linearised per-edit)"` ← hook auto-moves this file to `done/` on commit
