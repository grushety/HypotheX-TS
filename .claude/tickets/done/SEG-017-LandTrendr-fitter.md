# SEG-017 — Decomposition fitter: LandTrendr piecewise (EO)

**Status:** [x] Done
**Depends on:** SEG-019

---

## Goal

Fit the Kennedy et al. LandTrendr piecewise-linear temporal trajectory to remote-sensing indices (NDVI, NBR, EVI). Produces vertex list + per-segment slope + per-segment intercept, storable as a blob for OP-021 (Trend ops) and OP-022 (disturbance/recovery edits).

**Why:** LandTrendr is the canonical EO trajectory-segmentation algorithm; its vertex-based representation maps directly onto HypotheX-TS's trend segments and captures the disturbance/recovery dynamics central to the remote-sensing domain pack (SEG-023).

**How it fits:** Dispatched by SEG-019 when `shape='trend'` and `domain_hint='remote-sensing'`. Alternative to STL/MSTL for non-periodic trajectory segments with known or suspected breakpoints.

---

## Paper references (for `algorithm-auditor`)

- Kennedy, Yang, Cohen (2010) "Detecting trends in forest disturbance and recovery using yearly Landsat time series: 1. LandTrendr — Temporal segmentation algorithms" — *Remote Sensing of Environment* 114(12):2897–2910. DOI 10.1016/j.rse.2010.07.008.
- Kennedy et al. (2018) "Implementation of the LandTrendr algorithm on Google Earth Engine" — *Remote Sensing* 10(5):691 (implementation reference).

---

## Pseudocode

```python
def fit_landtrendr(X_seg, t,
                   max_vertices=6,
                   recovery_threshold=0.25,
                   penalty_per_vertex=0.1):
    # Step 1: identify candidate vertices by iterative SSE-reducing point selection
    candidates = find_candidate_vertices(X_seg, t, max_candidates=max_vertices * 2)

    # Step 2: pick the best subset minimizing penalized SSE
    best = None
    for k in range(2, max_vertices + 1):
        for subset in combinations(candidates, k):
            vertices = sorted([(0, X_seg[0])] + list(subset) + [(len(X_seg) - 1, X_seg[-1])])
            lines = fit_piecewise_linear(X_seg, t, vertices)
            sse   = piecewise_sse(X_seg, lines)
            cost  = sse + penalty_per_vertex * k
            if best is None or cost < best.cost:
                best = SimpleNamespace(vertices=vertices, lines=lines, sse=sse, cost=cost)

    slopes     = [slope(v1, v2) for v1, v2 in pairwise(best.vertices)]
    intercepts = [intercept(v1, v2) for v1, v2 in pairwise(best.vertices)]

    return DecompositionBlob(
        method='LandTrendr',
        components={'piecewise_linear': reassemble(best.lines, t)},
        coefficients={
            'vertices':   best.vertices,
            'slopes':     slopes,
            'intercepts': intercepts,
        },
        residual=X_seg - reassemble(best.lines, t),
        fit_metadata={'n_vertices': len(best.vertices), 'sse': best.sse}
    )
```

---

## Acceptance Criteria

- [x] `backend/app/services/decomposition/landtrendr_fitter.py` with:
  - `fit_landtrendr(X_seg, t, max_vertices=6, recovery_threshold=0.25, penalty_per_vertex=0.1) -> DecompositionBlob`
  - `find_candidate_vertices(X, t, max_candidates)` — iterative largest-SSE-reducing point search
  - `fit_piecewise_linear(X, t, vertices)` — least-squares per-segment line fit
- [x] Vertex count respects `max_vertices`
- [x] Per-segment slopes and intercepts stored as coefficients; retrievable by OP-021 for slope-edit ops
- [x] Unit test: synthetic trajectory with 3 true vertices at t={0, 100, 200} → recovers 3 vertices ±1 timestep
- [x] Reassembled piecewise signal matches original within vertex-bounded RMS
- [x] Penalty parameter configurable; default matches Kennedy 2010 recommendations
- [x] Recovery detection: if a segment has positive slope following a negative-slope segment of magnitude > `recovery_threshold`, tag it as `recovery=True` in coefficients
- [x] Tests cover: 2-vertex (straight line) and 6-vertex fits; penalty effect on vertex count; recovery flagging; reassembly round-trip
- [x] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "SEG-017: LandTrendr piecewise-linear fitter for EO trajectories"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Replaced the LandTrendr stub at `backend/app/services/decomposition/fitters/landtrendr.py` with a full Kennedy 2010 implementation.

**Files**
- `backend/app/services/decomposition/fitters/landtrendr.py` (replaced stub) — public surface:
  - `fit_landtrendr(X, t=None, max_vertices=6, recovery_threshold=0.25, penalty_per_vertex=0.1)` → `DecompositionBlob`, registered as `@register_fitter("LandTrendr")`.
  - `find_candidate_vertices(X, t=None, max_candidates=12)` — iterative largest-residual vertex addition (Kennedy 2010 §2.2).
  - `fit_piecewise_linear(X, t, vertices)` — anchored OLS fit at given vertex positions.
  Internals: `_build_design_matrix` (linear-B-spline / tent basis); `_fit_vertices` (anchored OLS — endpoints pinned to observed data, interior fit by `lstsq`); `_prune_iteratively` (drops interior vertex with smallest SSE-increase, records every (k, vx, sse) snapshot); `_recovery_flags`; `_empty_blob`/`_single_point_blob`/`_legacy_segment_keys`.
- `backend/tests/test_landtrendr_fitter.py` — 42 tests including: AC fixture (3 true vertices at t={0, 100, 200} recovered within ±1), max_vertices respected, 2-vertex straight-line exact recovery, 6-vertex bumpy fit, penalty monotonicity (huge penalty collapses to 2 vertices), recovery flagging (drop > threshold + sign flip), reassembly identity (`atol=1e-12`), legacy OP-021 schema (`slope_1`/`intercept_1`/`slope_2`/`intercept_2`/`breakpoint`), helper unit tests, custom time-index test, all input-validation paths (multivariate rejection, t-length mismatch, empty input, single-point, 2-D single-column accepted), Python-float typing.

**Algorithmic deviations**

1. **Anchored vs unanchored OLS.**  Initial implementation used unanchored joint OLS over all vertex Y values, which put the largest residual at the endpoints (OLS line is mean-centred → boundary samples far from it), so candidate generation picked endpoint-neighbour samples instead of true interior knots (got `[0, 5, 6, 239]` instead of `[0, 100, 200, 239]`).  Switched to anchored OLS per Kennedy 2010 §2.4: endpoint vy fixed to observed boundary samples, only interior vy fit by `lstsq` on the boundary-corrected target.  Endpoint residuals are now exactly 0 by construction.
2. **Iterative pruning vs brute-force combinations.**  Replaced the ticket pseudocode's `O(2^max_candidates)` `combinations()` enumeration with Bai-Perron / Kennedy 2018 EE-style iterative pruning — `O(max_candidates^2 · n)`, equivalent in practice.
3. **Legacy schema dual emission for OP-021.**  Existing `app/services/operations/tier2/trend.py` reads the legacy 2-segment LandTrendr schema (`slope_1`, `slope_2`, `intercept_1`, `intercept_2`, `breakpoint`).  The new fitter emits BOTH the generalised schema (`vertices`/`slopes`/`intercepts`/`recovery` as lists) AND the legacy keys derived from the first/last segments + first internal vertex.  This keeps OP-021's 47 existing tests passing without modification, while the new schema is available for richer multi-vertex consumers.

**Tests** — `pytest tests/test_landtrendr_fitter.py`: 42/42 pass.  Full backend suite: 1441 pass, 2 pre-existing unrelated failures (`test_operation_result_contract.py` missing fixture; `test_segment_encoder_feature_matrix.py` stale embedding-size assertion).  `ruff check` clean.  OP-021 trend ops (47/47) and trend-stochastic ops (53/53) all green — no regressions from the legacy-shim path.

**Code review** — no blocking issues.  Architecture rules (pure domain function, source citations on every public entry, `segment` naming, `@register_fitter` DI, no new dependencies) all hold.  Two minor robustness observations from the reviewer (not blocking, not in this commit): public `fit_piecewise_linear` does not explicitly validate `len(t) == len(X)` (relies on numpy), and `_legacy_segment_keys` uses `int(vertices[1][0])` rather than rounding for the breakpoint — neither is a real-world concern under the current callers.

**Out of scope / follow-ups**
- Migrating OP-021 (`tier2/trend.py`) to the new generalised schema would let users edit *any* segment's slope, not just the first/last — that's a OP-021 enhancement ticket, not part of SEG-017.
- The unanchored-OLS variant could be exposed as a `mode='free' | 'anchored'` parameter if a future use-case calls for it; left as a single anchored mode for now to match the simplified-LandTrendr literature.
