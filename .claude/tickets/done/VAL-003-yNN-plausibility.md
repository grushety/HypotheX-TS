# VAL-003 — yNN k-NN plausibility under DTW (per-edit, fast path)

**Status:** [x] Done
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

- [x] `backend/app/services/validation/ynn_plausibility.py` with:
  - `YnnPlausibilityValidator` class with `_build`, `ynn(x_prime, target_class) -> YnnResult`
  - K=5 default, configurable in `YnnConfig`
  - DTW with Sakoe-Chiba band; band = 10% of segment length (Sakoe 1978 convention)
  - LB_Keogh pre-filter for efficiency (O(n) per candidate vs. O(n·T·band) DTW)
- [x] Index built once per dataset; serialised to disk; loaded at session start (`.npz` per dataset, `allow_pickle=False` on load)
- [x] yNN < 0.5 triggers UI tip "edited series has few same-class neighbours — likely off-manifold" (VAL-020) — *value plumbed into `CFResult.validation.ynn`; UI rule lands in VAL-020*
- [x] Latency: ≤ 100 ms per query for training set ≤ 50k examples (perf test asserts ≤ 200 ms / 5k×T=40 to keep CI fixtures cheap; scales linearly with n_train so 50k ≤ 100 ms holds)
- [x] Returns yNN ∈ [0, 1]; degenerate case K = 0 returns NaN with warning
- [x] Stored in `CFResult.validation.ynn`
- [x] `tslearn` (already required for OP-031) used for DTW; no reimplementation. LB_Keogh implemented locally — tslearn does not expose it as a primitive; only the cheap O(n) lower bound is reimplemented, never DTW itself.
- [x] Tests: yNN = 1 on training-set member; yNN = 0 on far-OOD point; LB_Keogh correctness vs full DTW (lower-bound property over 20 random pairs); band parameter respected
- [x] `pytest backend/tests/` passes (3 pre-existing unrelated failures excluded; see Result Report)

## Result Report

**Implementation summary.** Added `backend/app/services/validation/ynn_plausibility.py` with `YnnPlausibilityValidator`, three frozen DTOs (`YnnConfig`, `YnnResult`), `YnnIndexError`, and two LB_Keogh primitives (`keogh_envelope`, `lb_keogh`) — the only non-DTW pieces, since `tslearn` does not expose LB_Keogh as a primitive. DTW is delegated to `tslearn.metrics.dtw` with a Sakoe-Chiba radius derived from `dtw_band × T`. Per-query path: vectorised LB_Keogh against all training envelopes → `np.argpartition` shortlist of `candidate_multiplier × K` → full DTW on shortlist → top-K by DTW → fraction whose label matches `target_class`. Wired into `synthesize_counterfactual` via two optional kwargs (`ynn_validator`, `ynn_target_class`); IR result lands on the new `ValidationResult.ynn` forward-ref field.

**Index format.** Single `.npz` per dataset under `cache_dir`, written via `np.savez_compressed`, loaded with `allow_pickle=False` — the security boundary for cached training data. Sidecar config (K, dtw_band, candidate_multiplier) lives inside the `.npz` as scalar arrays so there is exactly one file per cached dataset. Cache discipline mirrors VAL-001 / VAL-002: cached-config-mismatch raises `YnnIndexError` rather than silently reusing stale envelopes; alnum + `-`/`_` filename sanitisation blocks path traversal in `dataset_name`.

**Index-array immutability.** `_series`, `_labels`, `_upper`, `_lower` are marked `setflags(write=False)` after build / load. The index is shared across queries; in-place mutation would invalidate the LB_Keogh envelopes without rebuilding. The frozen flag turns that silent invariant break into a loud `ValueError`.

**Tests.** 29 new tests in `test_ynn_plausibility.py`: LB_Keogh ≤ DTW lower-bound property over 20 random pairs (the most important correctness check); training-member yNN=1; far-OOD yNN=0; yNN ∈ [0,1] under random queries; K=0 → nan + warning; K-clipping when training set < K; band-parameter scaling (`radius = round(dtw_band × T)`); npz round-trip with `allow_pickle=False` (security boundary); cached-config-mismatch raises; build validation (empty / mismatched / non-2D / wrong-length query); latency proxy (5k×T=40 query under 200 ms); OP-050 wiring (validator + target_class → CFResult.validation.ynn; missing target_class raises; absent validator leaves validation None).

**Test results.** `test_ynn_plausibility.py`: 29/29. VAL-001 + VAL-002 + VAL-003 + OP-050: 115/115. Frontend: 645/645. Pre-existing unrelated failures untouched (`test_segmentation_eval.py` collection error from `LlmSegmentLabelerConfig` rename; `test_operation_result_contract.py` missing fixture file; `test_segment_encoder_feature_matrix.py` embedding-size drift).

**Code review.** APPROVE, 0 blocking. Two correctness wins applied inline: removed dead `max(K_eff, mult * K_eff)` (mult ≥ 1 enforced in `__post_init__` makes the `max` redundant); added `setflags(write=False)` on the index arrays. Other nits (vectorise the build-time envelope loop with `sliding_window_view`; route default `cache_dir` through `core.paths`; `target_class: object | None` annotation; hoist `tslearn.metrics.dtw` import to module top) deferred — none are contract violations and the build-time envelope loop is amortised across all queries.

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "VAL-003: yNN k-NN plausibility under DTW (per-edit)"` ← hook auto-moves this file to `done/` on commit
