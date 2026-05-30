# REWORK-06 — Plausibility meter (live edit-quality gauges)

**Status:** [ ] Done
**Depends on:** REWORK-04

---

## Goal

Wire the four edit-quality gauges to update **live** as the user edits, expressing
whether the current edit is a trustworthy probe or an off-manifold artifact:
**Validity** (did the output change), **Proximity** (how small), **Sparsity** (how
few points), **Plausibility** (how on-distribution). Red/amber/green; an
off-distribution edit must visibly warn.

---

## Task 0 — Recon (record in Result Report)

- [ ] Read `backend/app/services/validation/native_guide.py`,
      `ynn_plausibility.py`, `validity_rate.py`, `probe_ir.py`. Document each
      function's signature, inputs, and the metric it returns.
- [ ] Check whether these are already invoked per-edit in `cf_coordinator.py` (they
      are imported there) — determine if results are surfaced to the UI or only used
      internally for projection.

## Backend verification

- [ ] Each gauge maps to a real, cited metric:
  - **Validity** → `validity_rate.py` (VAL-012): output actually changed.
  - **Proximity + Sparsity** → `native_guide.py` (VAL-004): Native Guide
    (Delaney et al. 2021) proximity (L2/normalized) + sparsity (fraction of points
    changed) — current SOTA proximity/sparsity formulation for TS CF.
  - **Plausibility** → `ynn_plausibility.py` (VAL-003): y-NN plausibility (fraction of
    k nearest neighbours sharing the CF class), the standard plausibility proxy.
- [ ] Confirm thresholds (`NativeGuideThresholds`) come from config, not magic numbers.

## Acceptance Criteria

- [ ] Gauges recompute on each applied edit and reflect backend values (no JS
      re-derivation of the metric).
- [ ] Off-distribution / low-plausibility edit shows a clear warning state.
- [ ] Confident, in-distribution edit shows green/calm.
- [ ] Empty (no edit yet) state shows dormant gauges, not zeros pretending to be data.
- [ ] Each gauge has a tooltip naming its metric + reference.

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "REWORK-06: live plausibility meter"`

## Result Report
<!-- metric→function map with references, threshold source, files touched -->
