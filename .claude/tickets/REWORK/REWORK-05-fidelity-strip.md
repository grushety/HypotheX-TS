# REWORK-05 — Fidelity "Model sees this" strip

**Status:** [ ] Done
**Depends on:** REWORK-02, REWORK-04

---

## Goal

Add the trust feature: a compact "Model sees this" strip showing the **exact
preprocessed series** fed to the model (after normalization / resampling / windowing),
so the scientist can verify the edited series reaches the model as intended. Expandable
to a preview comparing raw-edited vs. model-input series. This guards against the
single most insidious what-if failure: silent preprocessing mismatch.

---

## Task 0 — Recon (record in Result Report)

- [ ] Read `backend/app/services/inference.py` (`_vectorize_sample`,
      `_resample_vector`, prototype normalization) and trace the FULL transform chain
      applied between user-edited series and model input.
- [ ] Determine whether the post-transform array is currently exposed by any endpoint.
      Document: exposed / not exposed.

## Backend verification (likely sub-task here)

- [ ] If the preprocessed input is NOT already returned, add a field to the prediction
      response (or a thin `GET`/flag) that returns the exact array the model consumed,
      plus the ordered list of transforms applied (name + params). Logic in
      inference service; route stays thin.
- [ ] The strip must reflect the REAL transform chain — not a re-implementation in JS.
      Single source of truth = the backend transform path.

## Acceptance Criteria

- [ ] Collapsed: a one-line "Model sees this · N transforms · ✓ compatible" strip.
- [ ] Expanded: overlay/preview of raw-edited series vs. exact model-input series, and
      the named transform list.
- [ ] If a compatibility/shape mismatch exists, the strip warns clearly (ties into the
      existing `CompatibilityValidator`).
- [ ] Values come from backend, verified identical to what `PredictionService` uses.

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "REWORK-05: fidelity model-sees-this strip"`

## Result Report
<!-- transform chain documented, exposed-or-added decision, files touched -->
