# REWORK-10 — Cohort confirmation mode

**Status:** [ ] Done
**Depends on:** REWORK-02, REWORK-06

---

## Goal

Add the cohort/confirmation view: apply the **same semantic operation across N series**
and show **aggregated deltas** — flip rate, per-series movement (dumbbell plot vs. the
decision boundary), Δ-magnitude distribution, biggest mover. This turns an anecdote
(single-series exploration) into evidence, and directly serves the cherry-picking and
paper-readiness concerns. Net-new batch backend + new view. Design source:
`01-v2-cohort.png`.

---

## Task 0 — Recon (record in Result Report)

- [ ] Confirm there is NO batch/cohort endpoint (current `invoke` + CF coordinator are
      single-segment/single-sample).
- [ ] Read `services/datasets.py` to confirm how to enumerate a split's samples for the
      cohort set.

## Algorithm & SOTA justification (pick + document)

- **Aggregation:** per-series Δ (toward/away from boundary) + flip indicator, then
  cohort statistics: flip rate, mean Δ, Δ distribution.
- **"Is the effect real, not cherry-picked?"** — reuse the existing repo machinery:
  **PROBE invalidation rate** (`probe_ir.py`, VAL-002) and **Cherry-picking risk**
  (`cherry_picking.py`, VAL-013). Report a bootstrap CI on the cohort flip-rate / mean-Δ
  (stationary/moving-block bootstrap already in repo: `mbb.py`, VAL-031) so the
  aggregate carries a confidence interval, not just a point estimate. This is the
  defensible, paper-ready framing.

## Backend (new)

- [ ] New service `cohort_apply(operation, params, sample_ids, model) -> per-series
      results + aggregates (flip_rate, mean_delta, distribution, CI)`.
- [ ] New thin route `POST /api/cohort/apply`.
- [ ] Reuse single-series CF + prediction per sample in a loop; aggregate + bootstrap CI
      in the service. No model retraining.

## Acceptance Criteria

- [ ] "Cohort" mode reachable from the top-bar mode switch; same three-zone grammar.
- [ ] User picks one operation + magnitude, applies across the chosen cohort.
- [ ] Outcome panel: flip count/rate, mean Δ (with CI), biggest mover, held class.
- [ ] Per-series dumbbell plot sorted by Δ, decision-boundary line, FLIP tags.
- [ ] Δ-magnitude distribution histogram.
- [ ] Flip-rate / mean-Δ reported with bootstrap CI; cherry-picking risk surfaced.
- [ ] Reasonable performance / progress indicator for N series (cap or paginate if big).

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "REWORK-10: cohort confirmation mode"`

## Result Report
<!-- aggregation + CI method, perf approach, files touched -->
