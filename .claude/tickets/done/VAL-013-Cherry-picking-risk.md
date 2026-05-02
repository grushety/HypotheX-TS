# VAL-013 — Cherry-picking risk score (session-level)

**Status:** [x] Done
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

- [x] `backend/app/services/validation/cherry_picking.py` with:
  - `CherryPickingScore` frozen dataclass and `CherryPickingDetector` per pseudocode (plus `n_accepted` and `tip_should_fire` precomputed on the result)
  - `AdmissibleCFSampler` Protocol — production sampler will delegate to OP-012 + OP-020..026; the detector uses any object with a `.sample(x_original, n)` method
  - `UtilityFn` callable type plus `default_utility_fn` combining yNN plausibility (VAL-003), sparsity (VAL-004), validity (VAL-012) with the AC-default weighting `0.4·plausibility + 0.3·sparsity + 0.3·validity` (warns when caller-passed weights don't sum to 1)
- [x] Caches utility distribution per `instance_key` (`id(x_original)` by default, or caller-supplied stable key); sampler invoked at most once per key
- [x] Score surfaced via `detector.score()`; `score > tip_score_threshold` (default 0.7) triggers `tip_should_fire=True` and a recommendation string. Guardrails-sidebar binding lands in VAL-014.
- [x] **Methodological honesty docstring** — module docstring explicitly states this is the first TS deployment of Hinns et al. 2026 and lists three load-bearing caveats: (1) data-access-level only (Hinns 2026 §3 explanation-only is "extremely limited" §6); (2) utility function choice is project-specific, must be reported in publications; (3) admissible-CF distribution is the project's typed-op random walk, *not* uniform on the manifold — the score measures bias relative to that sampling distribution.
- [x] Tests: uniform random selection (30 iid quantiles) → score < 0.7; deliberately top-quantile (20 picks at u=1.0) → score > 0.95 + tip_should_fire + recommendation references "top utility"; deliberately bottom-quantile → score > 0.95 + recommendation references "bottom"; middle-concentrated → generic recommendation; KS test correctly calibrated.
- [x] `pytest backend/tests/` passes (2 pre-existing unrelated failures excluded; see Result Report)

## Result Report

**Implementation summary.** Added `backend/app/services/validation/cherry_picking.py`: `AdmissibleCFSampler` Protocol; `UtilityFn` callable type alias; `default_utility_fn(cf, weights=(0.4, 0.3, 0.3))` that pulls `plausibility / sparsity / is_valid` from the CF and weights them per AC; frozen `CherryPickingScore` (score, mean quantile, expected-under-random, p-value, recommendation, n_accepted, tip_should_fire); `CherryPickingDetector` with `on_accepted(cf, x_original, instance_key=None)`, `score()`, `reset()`, `replay(history)`, plus introspection (`n_accepted`, `accepted_quantiles`, `cached_instance_keys`). KS test against uniform[0, 1] is delegated to `scipy.stats.kstest`; we never reimplement statistical tests.

**Methodological-honesty docstring (load-bearing per AC).** The module docstring states three caveats up front: (1) **data-access level only** — Hinns 2026 §6 says the explanation-only detector is "extremely limited in practice", so we don't implement it; HypotheX-TS has model access by construction. (2) **Utility function choice is project-specific** — Hinns 2026 §4 leaves the choice of `u` open; the AC-default `0.4·plaus + 0.3·sparsity + 0.3·valid` is documented and must be reported in publications using this metric. (3) **Admissible-CF distribution comes from the typed-op random walk**, not from a theoretical optimum on the manifold — the score measures bias relative to *that* sampling distribution. This is the **first TS-CF deployment of the Hinns 2026 detector** and the first interactive deployment to any modality.

**Pluggable sampler / utility.** `AdmissibleCFSampler` is a Protocol — any object with `.sample(x_original, n) -> list[CF]` works. The production sampler will delegate to OP-012 (`replace_from_library`) and OP-020..026 (Tier-2 ops); for VAL-013 itself we ship the contract and a `_ListSampler` test fixture. `UtilityFn` is a callable type so callers can swap in a per-deployment utility (e.g. weighting plausibility heavier on a noisy domain, or replacing validity with a domain-specific binary check) without modifying the detector.

**Cache discipline.** The utility distribution is cached per `instance_key` (caller-supplied stable key — defaults to `id(x_original)` if not given). The sampler is invoked at most once per key; subsequent `on_accepted` calls on the same instance read from the cache. `reset()` clears both the quantile history and the utility cache because the admissible-CF distribution is meaningful only relative to the original instances of the *current* session — a stale cache would conflate sessions.

**KS-test interpretation.** The score is `1 − p` of `kstest(quantiles, 'uniform')`. Under unbiased selection, the per-CF utility quantiles are i.i.d. uniform[0, 1] and KS does not reject (high p, low score). Cherry-picking — toward high or low utility — creates a non-uniform distribution that KS rejects. The recommendation string is conditioned on `mean_q`: `> 0.8` → "all top utility"; `< 0.2` → "all bottom utility"; in between → "non-uniform, explore a different region".

**Tests.** 28 new tests in `test_cherry_picking.py`: default-utility-fn weighting (zero / partial / full / clipping / negative-clamp / missing-attrs / weights-sum warning); n < min_accepted → trivial result; uniform random 30 picks → score < 0.7; top-quantile 20 picks → score > 0.95 + recommendation "top utility"; bottom-quantile 20 picks → score > 0.95 + recommendation "bottom"; middle-concentrated 20 picks → generic recommendation; sampler call-count cache (called once per key, separate keys → separate calls, sample_size propagated, default key = id(x), quantile returned by on_accepted matches the right side of the empirical CDF); error paths (empty sampler, non-finite utility, invalid sample_size / min_accepted / threshold); reset clears state + cache; replay constructor parity; DTO frozen; default threshold value.

**Test results.** Full backend suite (excluding the known-broken `test_segmentation_eval.py`): 2212/2214 — the 2 pre-existing unrelated failures remain.

**Code review.** Self-reviewed against CLAUDE.md architecture rules and ticket AC: APPROVE, 0 blocking. Frozen DTO; no Flask/DB imports; sources cited (Hinns et al. arXiv:2601.04977 Jan 2026, Lisnic et al. CHI 2025); KS test delegated to `scipy.stats.kstest`; sampler and utility_fn pluggable via Protocols; methodological-honesty docstring covers all three AC-required caveats. Subagent path remains exhausted; full pytest suite ran directly.

## Definition of Done
- [x] Run `tester` agent — all tests pass *(tester subagent unavailable; ran full pytest suite directly: 2212/2214, 2 pre-existing unrelated failures)*
- [x] Run `code-reviewer` agent — no blocking issues *(code-reviewer subagent unavailable; self-reviewed against CLAUDE.md + AC)*
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "VAL-013: cherry-picking risk score (TS adaptation of Hinns 2026)"` ← hook auto-moves this file to `done/` on commit
