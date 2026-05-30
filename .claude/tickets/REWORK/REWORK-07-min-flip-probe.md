# REWORK-07 — Min-flip probe (smallest edit that changes the output)

**Status:** [ ] Done
**Depends on:** REWORK-02, REWORK-06

---

## Goal

Add a one-click probe that finds the **smallest edit that flips the model's output**
and reports the **distance to the decision boundary**, rendered as a ghost/dashed
overlay on the series plus a readout in OUTPUT. This is net-new backend work; it must
reuse the existing decomposition-first CF machinery and validation suite, not a new
parallel solver.

---

## Task 0 — Recon (record in Result Report)

- [ ] Read `backend/app/services/operations/cf_coordinator.py` fully. Document the
      coefficient-space edit path (`reassemble()`), the constraint/projection loop, and
      how a candidate edit is scored.
- [ ] Confirm the CF coordinator is single-segment and currently driven by a chosen
      Tier-2 op — i.e. there is no "search for minimal flip" entry point yet.

## Algorithm & SOTA justification (pick + document)

The minimal-flip probe is a **counterfactual search** minimizing edit cost subject to
a class-flip constraint. Project already cites Wachter 2017, DiCE, Native Guide,
Glacier, wCF, TSEvo. Recommended SOTA choice, in priority order:

1. **Primary — coefficient-space gradient/optimization counterfactual** consistent
   with the decomposition-first thesis: minimize `proximity + λ·sparsity` over the
   segment's decomposition coefficients subject to `argmax(f) ≠ baseline class`
   (classification) or `|Δ| ≥ τ` (regression). This is the natural, novel-contribution-
   aligned method (vs. raw-signal gradient baselines) and reuses `reassemble()`.
   Optimizer: projected gradient if the model is differentiable; otherwise NSGA-II /
   guided random search over coefficients (matches TSEvo's evolutionary framing).
2. **Fallback / sanity baseline — Native Guide** (Delaney et al. 2021): start from the
   nearest-unlike-neighbour and perturb toward it, CAM-weighted. Already in repo
   (`native_guide.py`); use as the comparison baseline and as a warm start.
- **Boundary distance** = the proximity metric (REWORK-06) of the minimal flip.
- Every candidate must pass through the existing plausibility/validity validators so
  the proposed flip is on-manifold — an implausible minimal flip is reported as such,
  not hidden.

## Backend (new)

- [ ] New service `min_flip` (in `services/operations/` or `services/validation/`)
      exposing `find_minimal_flip(sample, segment, model, config) -> {edit, distance,
      flipped_class, plausibility}`.
- [ ] New thin route (e.g. `POST /api/operations/min-flip`) delegating to it.
- [ ] Config-driven λ, max iterations, step — no magic numbers. Update `requirements.txt`
      only if a new optimizer dep is added (prefer existing numpy/torch).

## Acceptance Criteria

- [ ] "Min-flip" toggle in EVIDENCE → one click produces a result.
- [ ] Result = dashed/ghost overlay on the canvas showing the proposed minimal change.
- [ ] OUTPUT shows distance-to-boundary readout + the flipped class.
- [ ] Result passes (or is flagged by) the plausibility validators.
- [ ] Method choice + reference documented in the Result Report and context.md.
- [ ] Graceful "no flip found within budget" state.

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "REWORK-07: min-flip probe"`

## Result Report
<!-- chosen optimizer + why, boundary-distance definition, files touched -->
