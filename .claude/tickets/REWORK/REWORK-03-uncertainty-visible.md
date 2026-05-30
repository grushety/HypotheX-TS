# REWORK-03 — Uncertainty made visible

**Status:** [ ] Done
**Depends on:** REWORK-02

---

## Goal

Make prediction uncertainty *visible at a glance*, not buried as small text. A
near-tie or high-variance prediction must LOOK uncertain; a confident one must look
calm. Use the existing calibrated uncertainty + conformal machinery.

---

## Task 0 — Recon (record in Result Report)

- [ ] Read `backend/app/services/suggestion/uncertainty.py` (`score_uncertainty`) and
      `backend/app/services/validation/conformal_pid.py`; document what
      `fetchBenchmarkUncertainty` returns (margin, entropy, conformal interval/set).
- [ ] Confirm whether classification returns a conformal *prediction set* and
      regression returns a conformal *interval*.

## Backend verification

- [ ] Uncertainty endpoint returns calibrated values usable for display:
      classification → margin + entropy + conformal set; regression → prediction
      interval (lower/upper) at a stated coverage level. If coverage level isn't
      surfaced, expose it.

## Algorithm & SOTA justification

- **Conformal prediction (PID-controlled)** is already implemented (`conformal_pid.py`,
  VAL-001) — this is the current SOTA for *distribution-free, calibrated* uncertainty
  with finite-sample coverage guarantees, superior to raw softmax confidence which is
  known to be miscalibrated. **Do not replace it**; surface it. Entropy/margin are
  complementary cheap signals for the glance-level cue.

## Acceptance Criteria

- [ ] OUTPUT zone shows uncertainty that escalates visually only when the prediction
      is uncertain (e.g. probability bars express closeness; an indicator intensifies
      near a tie / wide interval).
- [ ] Classification: conformal set size and margin/entropy shown; a 2-class near-tie
      reads as uncertain instantly.
- [ ] Regression: conformal interval rendered as a band, not a bare point; stated
      coverage level visible.
- [ ] Confident prediction stays visually quiet (no false alarm).

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "REWORK-03: uncertainty made visible"`

## Result Report
<!-- uncertainty schema documented, coverage level, files touched -->
