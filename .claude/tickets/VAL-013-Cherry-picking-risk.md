# VAL-013 — Cherry-picking risk score (session-level)

**Status:** [ ] Done
**Depends on:** OP-050 (CF coordinator), VAL-001..008 (per-edit metrics)

---

## Goal

Implement a **TS-CF cherry-picking risk score** that quantifies the extent to which the CFs the user has displayed/accepted deviate systematically from the *u-optimal subset* of the admissible CF space. Operationalises Hinns et al. (arXiv 2601.04977, 2026) for time series — **a publishable research contribution** since the original is tabular-only.

**Why:** Hinns et al.'s explanation-only detector is "extremely limited in practice"; their data-access-level detector requires the auditor to query the model. HypotheX-TS has model access, so the data-access-level detector is feasible. Surfacing a real-time cherry-picking risk score is the **first deployment of this idea in interactive XAI**.

**How it fits:** Session-level metric. For each accepted CF, compute its utility-quantile within the admissible-CF distribution (sampled offline via OP-012 / OP-020..026). Aggregate to a session-level "displayed-CFs are systematically lower in u" statistic.

---

## Paper references (for `algorithm-auditor`)

- Hinns, Goethals, Van der Veeken, Evgeniou, Martens, **"On the Definition and Detection of Cherry-Picking in Counterfactual Explanations,"** arXiv 2601.04977 (Jan 8 2026).
- Lisnic, Cutler, Kogan, Lex, **"Visualization Guardrails,"** CHI 2025, DOI 10.1145/3706598.3713385.

---

## Pseudocode

```python
@dataclass(frozen=True)
class CherryPickingScore:
    score: float                       # ∈ [0, 1], higher = more suspicious
    accepted_quantile_mean: float      # Mean utility-quantile of accepted CFs
    expected_under_random: float       # Expected mean if user samples uniformly
    p_value: float                     # KS test against uniform [0, 1]
    recommendation: str | None

class CherryPickingDetector:
    def __init__(self, admissible_cf_sampler, utility_fn):
        self.sampler = admissible_cf_sampler   # Samples from E(x) per Hinns 2026 §3
        self.utility_fn = utility_fn           # u: CF → [0, 1] (combines plausibility, sparsity, validity)
        self.utility_distribution_cache = {}
        self.accepted_cfs = []

    def on_accepted(self, cf_result, x_original):
        u_accepted = self.utility_fn(cf_result)
        if x_original.id not in self.utility_distribution_cache:
            samples = self.sampler.sample(x_original, n=200)
            self.utility_distribution_cache[x_original.id] = [self.utility_fn(s) for s in samples]
        dist = self.utility_distribution_cache[x_original.id]
        quantile = np.mean([u <= u_accepted for u in dist])
        self.accepted_cfs.append((cf_result, quantile))

    def score(self) -> CherryPickingScore:
        if len(self.accepted_cfs) < 3:
            return CherryPickingScore(0, 0, 0.5, 1.0, None)
        quantiles = [q for _, q in self.accepted_cfs]
        # KS test against uniform[0, 1]: if user displays unbiased CFs, quantiles should be uniform
        from scipy.stats import kstest
        stat, p = kstest(quantiles, 'uniform')
        # High mean quantile = user is consistently selecting high-utility CFs (could be legit)
        # LOW mean quantile = user is consistently selecting low-utility CFs (suspicious / contrarian)
        # Either case rejects uniformity
        score_val = 1 - p                  # lower p → higher cherry-picking risk
        return CherryPickingScore(
            score=score_val,
            accepted_quantile_mean=float(np.mean(quantiles)),
            expected_under_random=0.5,
            p_value=float(p),
            recommendation=self._recommend(quantiles, score_val),
        )

    def _recommend(self, quantiles, score):
        if score < 0.5: return None
        m = np.mean(quantiles)
        if m > 0.8:  return "All CFs are top-utility — try one with intermediate plausibility for contrast"
        if m < 0.2:  return "All CFs are low-utility — surface the model's preferred CF for comparison"
        return "Quantile distribution is non-uniform — consider exploring a less-explored region"
```

---

## Acceptance Criteria

- [ ] `backend/app/services/validation/cherry_picking.py` with:
  - `CherryPickingScore` and `CherryPickingDetector` per pseudocode
  - `admissible_cf_sampler` plug-in interface (delegates to OP-012 + OP-020..026 to sample 200 admissible CFs per original instance)
  - `utility_fn` plug-in interface combining yNN plausibility (VAL-003), sparsity (VAL-004), validity (VAL-012); default weighting `0.4·plausibility + 0.3·sparsity + 0.3·validity`
- [ ] Cache utility distribution per original instance (computed once per first edit on that instance)
- [ ] Score surfaced in Guardrails sidebar (VAL-014); score > 0.7 triggers tip carrying the recommendation string (VAL-020)
- [ ] **Methodological honesty:** docstring explicitly states this is the first TS adaptation of Hinns et al. 2026 and lists its assumptions (data-access level, utility function chosen, sampling distribution from typed-op random walk)
- [ ] Tests: uniform random selection → score ≈ 0; deliberately top-quantile selection → score → 1; KS test correctly calibrated on synthetic uniform input
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "VAL-013: cherry-picking risk score (TS adaptation of Hinns 2026)"` ← hook auto-moves this file to `done/` on commit
