# SEG-017 — Decomposition fitter: LandTrendr piecewise (EO)

**Status:** [ ] Done
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

- [ ] `backend/app/services/decomposition/landtrendr_fitter.py` with:
  - `fit_landtrendr(X_seg, t, max_vertices=6, recovery_threshold=0.25, penalty_per_vertex=0.1) -> DecompositionBlob`
  - `find_candidate_vertices(X, t, max_candidates)` — iterative largest-SSE-reducing point search
  - `fit_piecewise_linear(X, t, vertices)` — least-squares per-segment line fit
- [ ] Vertex count respects `max_vertices`
- [ ] Per-segment slopes and intercepts stored as coefficients; retrievable by OP-021 for slope-edit ops
- [ ] Unit test: synthetic trajectory with 3 true vertices at t={0, 100, 200} → recovers 3 vertices ±1 timestep
- [ ] Reassembled piecewise signal matches original within vertex-bounded RMS
- [ ] Penalty parameter configurable; default matches Kennedy 2010 recommendations
- [ ] Recovery detection: if a segment has positive slope following a negative-slope segment of magnitude > `recovery_threshold`, tag it as `recovery=True` in coefficients
- [ ] Tests cover: 2-vertex (straight line) and 6-vertex fits; penalty effect on vertex count; recovery flagging; reassembly round-trip
- [ ] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "SEG-017: LandTrendr piecewise-linear fitter for EO trajectories"` ← hook auto-moves this file to `done/` on commit
