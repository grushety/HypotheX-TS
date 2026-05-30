# REWORK-02 — Output panel: Baseline / Current / Δ

**Status:** [ ] Done
**Depends on:** REWORK-01

---

## Goal

Build the OUTPUT zone — the missing center of the what-if tool. Show the model's
prediction on the **Baseline** (locked, original series) vs. **Current** (edited
series), with **Δ** as the full-width hero, including an unmissable class-flip flag.
Backend prediction already exists; this ticket assembles and correctly wires it.

---

## Task 0 — Recon (record in Result Report)

- [ ] Confirm `services/api/benchmarkApi.fetchBenchmarkPrediction` returns the
      normalized schema needed (task type, classes, probabilities, predicted_index,
      regression value). Read `backend/app/services/inference.py` +
      `backend/app/schemas/prediction.py` and document the exact response shape.
- [ ] Confirm `comparison/ModelComparisonPanel.vue` can be reused or must be
      replaced; note the gap.
- [ ] Identify the existing edit/apply hook in `BenchmarkViewerPage.vue` that fires
      after an operation (this drives Current recompute + stale state).

## Backend verification (must hold before frontend is "done")

- [ ] `PredictionService` returns, for the active sample, calibrated class
      probabilities (classification) or scalar/forecast (regression) via the
      declared inference adapter. If the normalized fields the UI needs are not all
      present, add them in the service/schema **in this ticket** (thin route stays
      thin).

## Acceptance Criteria

- [ ] Baseline prediction computed once on sample load and **locked** as reference.
- [ ] Current prediction recomputes after each applied operation.
- [ ] Δ block spans full width of the OUTPUT column (hero), shows per-class
      probability shift (classification) or signed numeric delta (regression).
- [ ] **Class flip** (argmax change) is visually unmistakable (color + icon + text).
- [ ] Four states implemented and reachable: **empty** (no sample), **loading**,
      **stale** (edited since last run → re-run affordance, never show old numbers as
      current), **error** (with retry).
- [ ] Classification and regression render modes both handled (whichever the active
      benchmark needs verified live; the other at least correct from schema).

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "REWORK-02: output panel baseline/current/delta"`

## Result Report
<!-- prediction schema documented, reuse vs rebuild decision, files touched -->
