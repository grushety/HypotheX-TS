# SEG-004 — Uncertainty scoring API

**Status:** [x] Done
**Depends on:** SEG-002

---

## Goal

Implement `score_uncertainty(X, S)` — the missing piece of the formal model API.
Returns per-timestep boundary uncertainty `u_t` and per-segment label uncertainty `u_seg`.

Paper spec (section 3.X.3):

- `u_t` — boundary uncertainty from variance of boundary scores around each proposed boundary
- `u_seg` — label uncertainty from spread of prototype distances (entropy of label probability distribution)

Expose via `GET /api/benchmarks/suggestion/uncertainty?dataset=...&split=...&sample_index=...`

---

## Acceptance Criteria

- [ ] `score_uncertainty(values, segments, boundary_scores) -> UncertaintyResult` function in
  `backend/app/services/suggestion/uncertainty.py`
- [ ] `UncertaintyResult` frozen dataclass: `boundary_uncertainty: tuple[float, ...]` (length T),
  `segment_uncertainty: tuple[float, ...]` (length K)
- [ ] Boundary uncertainty `u_t`: smooth the raw boundary score array with a Gaussian kernel (σ=2), return per-timestep
  value; near-zero outside boundary neighborhoods
- [ ] Segment uncertainty `u_k`: entropy of the label probability distribution `H(p(y|s)) = -sum(p log p)`; normalized
  to [0, 1] by dividing by log(|Y|)
- [ ] New Flask route `GET /api/benchmarks/suggestion/uncertainty` in `benchmarks.py`; returns
  `{boundary_uncertainty: [...], segment_uncertainty: [...]}`
- [ ] `BoundarySuggestionService.propose()` optionally includes uncertainty in the `SuggestionProposal` payload (new
  optional fields, not breaking)
- [ ] Tests cover: entropy 0 for certain prediction, entropy 1 for uniform distribution, boundary array length equals
  series length
- [ ] No new dependencies (scipy not required — implement Gaussian smoothing with NumPy)

## Definition of Done

- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent — entropy formula and boundary variance match paper spec
- [ ] Run `api-validator` agent — new route response shape correct
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "SEG-004: uncertainty scoring for boundaries and segment labels"`
- [ ] Update Status to `[x] Done`

## Work Done

- `backend/app/services/suggestion/uncertainty.py` — new module: `UncertaintyResult` frozen dataclass;
  `score_uncertainty(values, segments, boundary_scores)` → Gaussian-smoothed boundary uncertainty (σ=2, NumPy convolve,
  clipped to [0,1]) + normalised Shannon entropy per segment `H(p)/log(|Y|)`; source-cited internal helpers
  `_gaussian_kernel`, `_smooth_boundary_scores`, `_normalized_entropy`
- `backend/app/services/suggestion/boundary_proposal.py` — exposed `compute_boundary_scores(values, config)` as a public
  function (delegates to existing private `_compute_boundary_scores`; no existing behaviour changed)
- `backend/app/schemas/suggestions.py` — added optional `boundary_uncertainty` and `segment_uncertainty` fields (default
  None) to `SuggestionProposal`; `to_dict()` includes `boundaryUncertainty`/`segmentUncertainty` keys only when the
  fields are not None
- `backend/app/services/suggestions.py` — added `include_uncertainty: bool = False` parameter to
  `BoundarySuggestionService.propose()`; when True, calls `compute_boundary_scores` + `score_uncertainty` and attaches
  results to the returned `SuggestionProposal`
- `backend/app/routes/benchmarks.py` — added `GET /api/benchmarks/suggestion/uncertainty` route; returns
  `{boundary_uncertainty: [...], segment_uncertainty: [...]}`
- `backend/tests/test_uncertainty.py` — 37 tests covering: entropy 0 for certain prediction, entropy 1 for uniform,
  single/empty-label edge cases, Gaussian kernel properties (sums to 1, symmetric, odd length), smoothing preserves
  length and clips to [0,1], `score_uncertainty` length contracts, length mismatch raises, `compute_boundary_scores`
  shape, `propose(include_uncertainty=True)`d field presence and `to_dict` keys, route 200/400/404
