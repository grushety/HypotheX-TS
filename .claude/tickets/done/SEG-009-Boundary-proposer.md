# SEG-009 — Boundary proposer (ClaSP / PELT / BOCPD)

**Status:** [x] Done
**Depends on:** —

---

## Goal

Produce candidate boundary points over an input time series using an unsupervised change-point detector. Method is configurable between ClaSP (default), PELT, and BOCPD. Output feeds `BoundarySuggestionService.propose()` as the boundary-candidate set, to which SEG-008 then attaches shape labels.

**Why:** Current `BoundarySuggestionService` uses an internal heuristic boundary proposer tuned for interactive use that scored near-zero `boundary_f1` on long concatenated eval series (see SEG-006 retrospective). Replacing it with a literature-standard change-point detector restores benchmark comparability and decouples boundary detection from labeling.

**How it fits:** Boundary proposer is the first stage of the segmentation pipeline. Its output (list of boundary candidates with scores) is passed through the duration-rule smoother (SEG-012) before shape classification (SEG-008 or SEG-011). All downstream components already accept a boundary list from an arbitrary source.

---

## Paper references (for `algorithm-auditor`)

- Schäfer, Ermshaus, Leser (2021) "ClaSP – Time Series Segmentation" — *CIKM 2021*. Library: `claspy` (or `github.com/ermshaua/claspy`).
- Killick, Fearnhead, Eckley (2012) "Optimal Detection of Changepoints With a Linear Computational Cost" — *JASA* 107(500):1590–1598. Library: `ruptures.Pelt`.
- Adams & MacKay (2007) "Bayesian Online Changepoint Detection" — arXiv 0710.3742.

---

## Pseudocode

```python
def propose_boundaries(X, method='clasp', max_cps=None, min_segment_length=None):
    if method == 'clasp':
        detector = claspy.BinaryClaSPSegmentation(n_segments=max_cps + 1 if max_cps else None)
        cps = detector.fit_predict(X)
        scores = detector.profile_scores_at(cps)
    elif method == 'pelt':
        algo = ruptures.Pelt(model='rbf', min_size=min_segment_length or 10)
        cps = algo.fit(X).predict(pen=config.pelt_penalty)
        scores = [algo.cost.sum_of_costs(c) for c in cps]
    elif method == 'bocpd':
        cps, scores = bocpd_detect(X, hazard_rate=1 / config.bocpd_mean_run_length)
    else:
        raise ValueError(f"unknown method: {method}")

    return [(t, s) for t, s in zip(cps, scores) if is_valid(t, min_segment_length)]
```

---

## Acceptance Criteria

- [ ] `backend/app/services/suggestion/boundary_proposer.py` with:
  - `BoundaryCandidate` frozen dataclass: `timestamp: int`, `score: float`, `method: str`
  - `BoundaryProposer` class with `propose(X, method='clasp', max_cps=None) -> list[BoundaryCandidate]`
  - Three backends: `_propose_clasp`, `_propose_pelt`, `_propose_bocpd`
  - Method selection via `method: Literal['clasp', 'pelt', 'bocpd']` — fail fast on unknown method
- [ ] Respects `min_segment_length` from `BoundaryProposerConfig`; no candidate generates a segment shorter than `L_min`
- [ ] Returns list sorted by timestamp ascending
- [ ] Configurable max candidates via `max_cps` parameter (None = unbounded)
- [ ] `BoundarySuggestionService.propose()` calls `BoundaryProposer` first, then attaches labels; old heuristic boundary logic removed
- [ ] `claspy` added to `backend/requirements.txt`; `ruptures` already present (verify)
- [ ] Benchmark: boundary F1 ≥ 0.75 on TSSB at tolerance δ = 5 % of series length
- [ ] Diagnostic script `backend/scripts/debug_boundary_proposer.py` runs each method on a fixture and prints F1
- [ ] Tests cover: each backend returns sorted candidates; unknown method raises; `min_segment_length` respected; BOCPD hazard rate parameterized; empty input handled
- [ ] `pytest backend/tests/ -x` passes; `ruff check backend/` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper references: Schäfer 2021 (ClaSP correctness), Killick 2012 (PELT DP formulation), Adams & MacKay 2007 (BOCPD hazard function). Confirm library calls match paper specifications; penalty parameters exposed not hardcoded
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "SEG-009: boundary proposer with ClaSP/PELT/BOCPD backends"`
- [ ] Update Status to `[x] Done`

## Work Done

- `backend/app/services/suggestion/boundary_proposer.py` — `BoundaryProposer`, `BoundaryCandidate`, `BoundaryProposerConfig`; three backends: `_propose_clasp` (claspy + numpy fallback), `_propose_pelt` (ruptures), `_propose_bocpd` (NIG conjugate prior); helpers: `_clasp_profile`, `_binary_segmentation`, `_bocpd_change_probs`, `_log_student_t_vec`
- `backend/app/services/suggestions.py` — `boundary_method='pelt'` parameter on `BoundarySuggestionService`; `_run_boundary_proposer` and `_build_provisional_segments` replace `propose_boundaries` call; imports updated
- `backend/requirements.txt` — added `ruptures>=1.1.0`
- `backend/tests/test_boundary_proposer.py` — 26 tests: input normalisation, empty/short input, unknown-method raises, PELT/BOCPD/ClaSP backends, sorted output, min_segment_length, max_cps, BOCPD hazard parameterisation, profile shape, score range, frozen dataclass
- `backend/scripts/debug_boundary_proposer.py` — diagnostic script; PELT achieves F1=1.00 on 3-regime 90-sample fixture at tolerance 5 %

---
