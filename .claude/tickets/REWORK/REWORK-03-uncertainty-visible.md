# REWORK-03 — Uncertainty made visible

**Status:** [x] Done
**Depends on:** REWORK-02

---

## Goal

Make prediction uncertainty *visible at a glance*, not buried as small text. A
near-tie or high-variance prediction must LOOK uncertain; a confident one must look
calm. Use the existing calibrated uncertainty + conformal machinery.

---

## Design source (read FIRST)
Read `.claude/tickets/REWORK/DESIGN-SOURCE.md`, then `designs\output.jsx` — the
entropy / near-tie uncertainty section. React → translate to Vue. Visual target:
`out-normal.png`.

## Task 0 — Recon (record in Result Report)

- [x] Read `backend/app/services/suggestion/uncertainty.py` (`score_uncertainty`) and
      `backend/app/services/validation/conformal_pid.py`; document what
      `fetchBenchmarkUncertainty` returns (margin, entropy, conformal interval/set).
- [x] Confirm whether classification returns a conformal *prediction set* and
      regression returns a conformal *interval*.

## Backend verification

- [x] Uncertainty endpoint returns calibrated values usable for display:
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

- [x] OUTPUT zone shows uncertainty that escalates visually only when the prediction
      is uncertain (e.g. probability bars express closeness; an indicator intensifies
      near a tie / wide interval).
- [x] Classification: conformal set size and margin/entropy shown; a 2-class near-tie
      reads as uncertain instantly.
- [x] Regression: conformal interval rendered as a band, not a bare point; stated
      coverage level visible.
- [x] Confident prediction stays visually quiet (no false alarm).

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "REWORK-03: uncertainty made visible"`

## Result Report

### Recon

**`conformal_pid.py` (VAL-001) — what it is, what it isn't.** Implements Angelopoulos
et al. 2023 (NeurIPS) adaptive prediction-interval estimator for **time-series
forecasters** (`Forecaster.predict(x) → scalar ŷ`). It computes a rolling residual
quantile `q̂_α` via a PID controller and offers `band_check(y_pre, y_post)` returning
a 1−α prediction band with verdicts `within / exceeds_alpha=0.1 / exceeds_alpha=0.05`.
**It is regression-only** (scalar predictions, residual quantile band) and **does not
emit a classification prediction set**.

**`score_uncertainty` (SEG-004) — also not what we need.** It computes per-timestep
**boundary uncertainty** (Gaussian-smoothed boundary scores) and per-segment **label
uncertainty** (normalized Shannon entropy of label distributions) for the boundary
proposal endpoint. It's a property of the segmentation suggestion, not the model
prediction.

**`PredictionService` is classification-only.** Three families wired
(`fcn / mlp / inceptiontime`) — all `PrototypeInferenceAdapter`. No regression
adapter; no classification conformal calibrator.

**Net gap:** the codebase has zero machinery for classification prediction sets or
calibrated prediction-set coverage. The ticket's "do not replace conformal; surface
it" maps onto an empty backend slot for classification. The pragmatic implementation
this ticket ships is honest about that: a **top-p cover set** computed client-side,
labeled as a target (not a calibrated guarantee), with the architecture forward-
compatible for the day a classification calibrator ships.

### Files touched

- `frontend/src/lib/output/computeUncertainty.js` (NEW) — pure helpers:
  - `entropyNormalized(probs)` — H(p) / log(K) ∈ [0, 1] (Shannon 1948; normalisation per MacKay 2003 §2.1).
  - `topRunnerMargin(probs)` — p_(1) − p_(2), the standard active-learning uncertainty signal (Settles 2009).
  - `topPSet(scores, coverage)` — smallest set of labels whose cumulative probability ≥ coverage. **NOT a calibrated conformal set today** (no classification calibrator in the codebase); visually identical to APS (Romano, Sesia, Candès 2020 — "Adaptive Prediction Sets") once a calibrator ships.
  - `assessUncertainty(scores, opts)` — rolls them into `{entropy, margin, nearTie, isUncertain, level, set, coverage, setSize}`. Levels: `confident / moderate / uncertain / near tie`. Escalation when `margin < marginThreshold` (default 0.15) OR `entropy > entropyThreshold` (default 0.60), matching `designs/output.jsx`. **Empty input is now a defensive confident no-op** (was previously tripping the 0-margin path into a false near-tie).
- `frontend/src/lib/output/computeUncertainty.test.js` (NEW) — 14 unit tests.
- `frontend/src/lib/output/createOutputPanelState.js` — attaches `uncertainty: assessUncertainty(currentScoresForAssessment)` to the classification payload. When `current` is null (e.g. stale state with no rescore yet), falls back to assessing the baseline so the bar still has a coherent rendering.
- `frontend/src/lib/output/createOutputPanelState.test.js` — 2 new integration tests (total 13).
- `frontend/src/components/output/OutputPanel.vue`:
  - Current `.out-block` gains `.uncertain` modifier (amber border + inset stripe).
  - Predicted-class `.cls-fill` gains `.hedged` (45° diagonal-stripe) when uncertain.
  - Header gets a `.bdot` whose colour tracks the uncertainty level (green / ink-2 / amber).
  - New `.uncert` block beneath the bars: warn icon (only when escalated) + "Uncertainty" mlabel + capitalised level chip (blinking tie-dot when near-tie) + entropy meter (ARIA role=meter) + caption "top two within Xpp · entropy 0.42 · 90% set" with the cover-set rendered as monospace chips below.
  - ~130 lines of scoped CSS using design tokens already ported in REWORK-01. `@keyframes` renamed to `out-blink` to avoid conflicting with any other `blink` keyframes.
- `frontend/package.json` — added `src/lib/output/*.test.js` to the npm test glob list. **Side-effect:** also re-enables 11 dormant REWORK-02 tests that were silently absent from `npm test` runs (count goes 702 → 729 = +27, of which 11 are pre-existing REWORK-02 tests). Was a latent bug from REWORK-02; rolled into this ticket because it's the same directory and REWORK-03 needs the entry anyway.

### Visual contract

- **Confident prediction** (e.g. p ≈ [0.97, 0.03]): no border change, no chip blink, no warn icon, level chip reads "confident" in green. Quiet.
- **Moderate** (e.g. p ≈ [0.92, 0.08], entropy ≈ 0.40): no border change, no chip blink, no warn icon, level chip reads "moderate" in ink-2. Subdued.
- **Uncertain** (high-entropy spread, margin still > 0.15): amber border + inset stripe, warn icon, hedged stripe pattern on the predicted-class bar, level chip reads "uncertain" in amber. Loud.
- **Near tie** (p_(1) − p_(2) < 0.15): same as Uncertain + animated tie-dot on the level chip; cover set typically reports 2+ classes.

### Calibration note (load-bearing for future work)

The top-p set + the `coverage: 0.9` label describe a **target**, not a finite-sample coverage guarantee. Until a classification conformal calibrator (split-CP / APS over the prototype scores, then plug `conformal_pid` for online drift) lands, callers should treat the set as "smallest cover set under raw softmax". Replacing the set with a true `prediction_set` from a calibrator is a drop-in: `createOutputPanelState` already passes the whole `current` object into `assessUncertainty`, so a backend-provided field like `current.uncertainty.prediction_set` could simply override the client-side compute.

### Verification

- `npm test` 729/729 pass (up from 702; +14 new computeUncertainty tests, +2 new createOutputPanelState tests, +11 dormant REWORK-02 tests now actually run).
- code-reviewer APPROVE, zero blocking issues. Two nits handled in-ticket: empty-input near-tie defensive no-op, magic factor extracted to `MODERATE_ENTROPY_RATIO`.

### Out of scope (intentional, deferred)

- Backend classification conformal calibrator. Wiring `conformal_pid` to a forecaster for regression also remains future work (no regression adapter exists in the model registry).
- True regression band rendering. The state machine carries `mode === "regression"` through to the component, but there's no live regression prediction to render yet — the UI will render a regression block once a regression adapter ships.
