# VAL-003 — yNN k-NN plausibility under DTW (per-edit, fast path)

**Status:** [ ] Done
**Depends on:** OP-050 (CF coordinator), training-set k-d tree

---

## Goal

For each edited series x', compute the **k-NN plausibility metric** `yNN_K(x') = (1/K) Σ 1[ŷ(x_j) = ŷ(x')]` where x_j are the K nearest neighbours of x' under DTW distance with Sakoe-Chiba band. Returns the fraction of nearby training points sharing the CF's predicted class — a well-validated proxy for whether x' lies on the data manifold.

**Why:** A CF that is technically valid (flips the model) but lies in a region with no training-set neighbours of the target class is implausible. yNN catches off-manifold CFs without requiring a generative model. Validated for TS in TSEvo, Glacier, and CONFETTI.

**How it fits:** Fast-path metric. Pre-built k-d tree (or HNSW index for DTW) on training set indexed by class. Per edit: query top-K neighbours, count target-class fraction, return.

---

## Paper references (for `algorithm-auditor`)

- Pawelczyk et al., **"CARLA,"** NeurIPS 2021 D&B, arXiv 2108.00783 (defines yNN).
- Höllig, Kulbach, Thoma, **"TSEvo: Evolutionary Counterfactual Explanations for TSC,"** ICMLA 2022, DOI 10.1109/ICMLA55696.2022.00013.
- Wang, Samsten, Miliou, Mochaourab, Papapetrou, **"Glacier,"** *Machine Learning* 113:4639 (2024), DOI 10.1007/s10994-023-06502-x.
- Sakoe & Chiba (1978) for warping band — *IEEE ASSP* 26(1):43.

---

## Pseudocode

```python
class YnnPlausibilityValidator:
    def __init__(self, training_set, K=5, dtw_band=0.1):
        self.training_set = training_set
        self.K = K
        self.dtw_band = dtw_band              # Sakoe-Chiba radius as fraction
        self._build_index()

    def _build_index(self):
        # For DTW: precompute LB_Keogh envelopes; brute force with band for MVP
        self.envelopes = [(lower_bound_keogh(x.X, self.dtw_band), x) for x in self.training_set]

    def ynn(self, x_prime, target_class) -> float:
        from tslearn.metrics import dtw
        # Triangle-inequality pruning via LB_Keogh, then DTW on candidates
        candidates = lb_keogh_filter(self.envelopes, x_prime, top_k=4*self.K)
        dists      = sorted(
            [(dtw(x_prime, c.X, sakoe_chiba_radius=int(self.dtw_band * len(x_prime))), c)
             for _, c in candidates],
            key=lambda p: p[0]
        )[:self.K]
        agree = sum(1 for _, c in dists if c.label == target_class)
        return agree / self.K
```

---

## Acceptance Criteria

- [ ] `backend/app/services/validation/ynn_plausibility.py` with:
  - `YnnPlausibilityValidator` class with `_build_index`, `ynn(x_prime, target_class) -> float`
  - K=5 default, configurable in `YnnConfig`
  - DTW with Sakoe-Chiba band; band = 10% of segment length (Sakoe 1978 convention)
  - LB_Keogh pre-filter for efficiency (O(n) per candidate vs. O(n²) DTW)
- [ ] Index built once per dataset; serialised to disk; loaded at session start
- [ ] yNN < 0.5 triggers UI tip "edited series has few same-class neighbours — likely off-manifold" (VAL-020)
- [ ] Latency: ≤ 100 ms per query for training set ≤ 50k examples (asserted by perf test)
- [ ] Returns yNN ∈ [0, 1]; degenerate case K = 0 returns NaN with warning
- [ ] Stored in `CFResult.validation.ynn`
- [ ] `tslearn` (already required for OP-031) used for DTW; no reimplementation
- [ ] Tests: yNN = 1 on training-set member; yNN = 0 on far-OOD point; LB_Keogh correctness vs full DTW; band parameter respected
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper refs Pawelczyk CARLA 2021 (yNN definition), Sakoe & Chiba 1978 (band), Glacier 2024 (TS application). Confirm DTW band is paper-correct; LB_Keogh pruning preserves top-K correctness; K and band configurable
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "VAL-003: yNN k-NN plausibility under DTW (per-edit)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
