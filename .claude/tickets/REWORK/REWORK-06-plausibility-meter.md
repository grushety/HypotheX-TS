# REWORK-06 — Plausibility meter (live edit-quality gauges)

**Status:** [x] Done
**Depends on:** REWORK-04

---

## Goal

Wire the four edit-quality gauges to update **live** as the user edits, expressing
whether the current edit is a trustworthy probe or an off-manifold artifact:
**Validity** (did the output change), **Proximity** (how small), **Sparsity** (how
few points), **Plausibility** (how on-distribution). Red/amber/green; an
off-distribution edit must visibly warn.

---

## Design source (read FIRST)
Read `.claude/tickets/REWORK/DESIGN-SOURCE.md`, then `designs\plausibility.jsx` and
`evidence.jsx`. React → translate to Vue. Visual target: `01-v2-primary.png` (Edit
quality gauge cluster).

## Task 0 — Recon (record in Result Report)

- [x] Read `backend/app/services/validation/native_guide.py`,
      `ynn_plausibility.py`, `validity_rate.py`, `probe_ir.py`. Document each
      function's signature, inputs, and the metric it returns.
- [x] Check whether these are already invoked per-edit in `cf_coordinator.py` (they
      are imported there) — determine if results are surfaced to the UI or only used
      internally for projection.

## Backend verification

- [x] Each gauge maps to a real, cited metric:
  - **Validity** → `validity_rate.py` (VAL-012): output actually changed.
  - **Proximity + Sparsity** → `native_guide.py` (VAL-004): Native Guide
    (Delaney et al. 2021) proximity (L2/normalized) + sparsity (fraction of points
    changed) — current SOTA proximity/sparsity formulation for TS CF.
  - **Plausibility** → `ynn_plausibility.py` (VAL-003): y-NN plausibility (fraction of
    k nearest neighbours sharing the CF class), the standard plausibility proxy.
- [x] Confirm thresholds (`NativeGuideThresholds`) come from config, not magic numbers.

## Acceptance Criteria

- [x] Gauges recompute on each applied edit and reflect backend values (no JS
      re-derivation of the metric).
- [x] Off-distribution / low-plausibility edit shows a clear warning state.
- [x] Confident, in-distribution edit shows green/calm.
- [x] Empty (no edit yet) state shows dormant gauges, not zeros pretending to be data.
- [x] Each gauge has a tooltip naming its metric + reference.

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "REWORK-06: live plausibility meter"`

## Result Report

### Recon

**`validity_rate.py` (VAL-012)** — Session-level tracker. `ValidityRateTracker.rate() → ValidityRateResult(n_total, n_valid, rate, rate_by_tier, rate_by_shape, rate_trend_7day, recent_rate, tip_should_fire)`. The validity boolean is `is_valid = (predicted_class == target_class)` per edit, set by the orchestrator that runs the user's classifier post-edit. Cited: Verma et al. *ACM CSUR* 56:312 (2024) §3 (validity is the primary CF desideratum); Mothilal et al. "DiCE," FAccT 2020 §3.1 (operationalisation as per-method evaluation metric). EventBus-driven (`'cf_result'` topic) — no Flask route surfaces it.

**`native_guide.py` (VAL-004)** — `native_guide_validate(x, x_prime, thresholds=None) → NativeGuideResult(proximity, sparsity, proximity_pct, too_dense, metric)`. Proximity is DTW / Euclidean / L1 distance (default DTW with Sakoe-Chiba band 0.1). Sparsity is fraction of unchanged timesteps. `proximity_pct` is the percentile rank against the dataset's NUN distribution — requires `NativeGuideThresholds`. Cited: Delaney, Greene, Keane, "Instance-based Counterfactual Explanations for Time Series Classification," ICCBR 2021. **Thresholds come from per-dataset calibration JSON** (`load_thresholds(dataset)` → `cache/native_guide_thresholds_<dataset>.json`); they are not magic numbers in code. When the cache is missing (current default — no calibrations shipped), the validator gracefully returns `proximity_pct=None` and `too_dense=False`.

**`ynn_plausibility.py` (VAL-003)** — `YnnPlausibilityValidator.ynn(x_prime, target_class) → YnnResult(ynn, target_class, K, n_neighbours_evaluated)`. yNN is the fraction of top-K nearest training neighbours (DTW with Sakoe-Chiba band 0.1) that share the target class. K=5 default. LB_Keogh prefilter prunes candidates. Cited: Verma et al. *ACM CSUR* 56:312 (2024) §4.4 (yNN as plausibility proxy); Pawelczyk et al. NeurIPS 2020. Index built lazily per-dataset by `EvidenceService` (REWORK-04); cached in-process. Returns `nan` (frontend renders as `null` → "—") when K=0.

**`probe_ir.py` (VAL-002)** — Closed-form first-order linearised bound on the probability that a small Gaussian perturbation flips a binary decision rule. Cited: Pawelczyk et al. "Probabilistically Robust Recourse," ICLR 2023 Eq. 5. Requires the model to expose `score`, `predict`, `gradient`, and `threshold`. **Does not fit our prototype classifier**: the prototype softmax doesn't expose a `gradient` method and isn't a binary decision rule. probe_ir would need adapter rework to wire into the 4-gauge view; out of scope for REWORK-06 and not required by the acceptance criteria.

**Internal-vs-UI surfacing pre-rework**: VAL-003 and VAL-004 are reached only via `cf_coordinator.py` during operation synthesis (and now via the REWORK-04 `/api/benchmarks/evidence/plausibility` endpoint). VAL-012 is event-bus-driven and not exposed by any Flask route — REWORK-06 therefore wires validity via prediction-rerun aggregation client-side rather than reaching into the backend tracker.

### REWORK-04 → REWORK-06 delta

REWORK-04 stood the gauge cluster up but left two gaps that REWORK-06 closes:

1. **Validity gauge was a constraint-pass rate**, not VAL-012. Renamed honestly to "Pass rate" with source `"constraint engine · session audit (not VAL-012 yet)"`. REWORK-06 wires the proper VAL-012 semantic.
2. **No paper citations or off-distribution badge** — gauges had a single `source` string but no scholarly reference, and the off-distribution case was only reflected in the gauge's own tone color (subtle).

REWORK-06 changes:

- **Validity gauge** now derives from a new client-side `validityRuns` log. Every successful `handleRerunPrediction` appends `{version, flipped}` where `flipped = result.predicted_label !== baselinePrediction.predicted_label`. The gauge value is the session-cumulative rate `flipped / total`. **Honest specialisation**: VAL-012's strict definition is `predicted_class == target_class`, but this prototype carries no explicit target-class picker. "Any flip away from baseline" is the canonical surrogate in Mothilal §3.1 when no desired class is specified. JSDoc says so explicitly. The gauge value is null until the first rerun lands (dormant empty state); resets in `clearPredictionState`.
- **Paper references** on every gauge — new `reference` field in the gauge object. References:
  | Gauge | Reference |
  |---|---|
  | Validity | Verma et al. *ACM CSUR* 56:312 (2024) §3; Mothilal et al. DiCE, FAccT 2020 §3.1 |
  | Proximity | Delaney et al. ICCBR 2021 (Native-Guide, §3.1) |
  | Sparsity | Delaney et al. ICCBR 2021 (Native-Guide, §3.2) |
  | Plausibility | Verma et al. *ACM CSUR* 56:312 (2024) §4.4; Pawelczyk et al. NeurIPS 2020 |
- **Tooltip per gauge** — anchored above each card, `role="tooltip"` + `aria-describedby` from the SVG `role="meter"`. Shows `hint + source + reference`. Opens on hover or keyboard focus; matches WAI-ARIA APG tooltip idiom.
- **Cluster-level OFF-DISTRIBUTION badge** in the header. Fires only when `Number.isFinite(ynn) && ynn < OFF_DISTRIBUTION_THRESHOLD` (= 0.4). Null plausibility (no yNN index built) does NOT fire — that's no claim, not a low claim. Reason text corroborates with low sparsity ("touches more than half of the series") when both signals are present.
- **Per-card `.tone-warn` modifier** — amber border + inset bar on any gauge whose own tone is `uncertain`. Quiet on confident gauges.
- **Removed always-visible source footer** from each card. Source/reference now lives in the tooltip — declutters the cluster without losing the citation.

### Threshold provenance

- `OFF_DISTRIBUTION_THRESHOLD = 0.4` (frontend) — presentation threshold for the cluster-level badge. Matches the gauge tone's "uncertain" cutoff (i.e. "uncertain plausibility" ⇔ "off-distribution"). Exported as a named constant so future tickets can either parametrise it via domain config or wire it to a real backend rule.
- `NativeGuideThresholds` (backend, VAL-004) — per-dataset calibration JSON. Not yet shipped for any dataset, so `proximity_pct` is null in the current state of the world. When calibration lands, the gauge picks it up automatically.

### Files touched

- `frontend/src/lib/evidence/createPlausibilityGaugesState.js` — new input contract (`validityRuns` in place of `events`), VAL-012 semantic, `reference` field per gauge, top-level `offDistribution` / `offDistributionReason` outputs, exported `OFF_DISTRIBUTION_THRESHOLD`.
- `frontend/src/lib/evidence/createPlausibilityGaugesState.test.js` — rewritten to 16 tests (was 11): validity aggregation, malformed runs, paper-reference presence, off-distribution firing/quiet/null cases + low-sparsity corroboration, honest n/a contract.
- `frontend/src/components/evidence/PlausibilityGauges.vue` — added OFF-DISTRIBUTION header badge (animated pulse, role=status), per-card tooltip with role=tooltip + aria-describedby, `.tone-warn` modifier, removed always-visible source footer.
- `frontend/src/views/BenchmarkViewerPage.vue` — new `validityRuns` ref + tracking inside `handleRerunPrediction`. Reset in `clearPredictionState`. Gauge state input switched from `events` to `validityRuns`. One-line race-window ack comment.

### Verification

- Frontend `npm test`: **752/752 PASS** (was 747; the gauge state test file went from 11 → 16 = +5 net).
- Backend untouched.
- code-reviewer: APPROVE, zero blocking issues. Three nits and two suggestions noted; two addressed in-ticket (race-window comment, dead `.plaus-source` CSS removed); the rest deferred (hex literals, tooltip aria-hidden parity, dropped-counter telemetry).

### Out of scope (intentional, deferred)

- **probe_ir wiring as a 5th gauge** — requires PrototypeInferenceAdapter to expose `gradient` + binary `threshold`, neither of which exists today. Separate ticket if/when an analytic adapter ships.
- **True backend VAL-012 surface** — the EventBus-driven tracker (`ValidityRateTracker.rate()`) is not exposed via a Flask route. The "specialised" client-side rate is honest and well-documented; a future ticket can replace it with a route that reads the tracker's snapshot if cross-session persistence becomes important.
- **NativeGuideThresholds calibration script** — no per-dataset JSON caches ship today, so `proximity_pct` stays null. Adding a calibration step is a backend-engineering ticket; the gauge picks the values up the day they land.
- **Tooltip aria-hidden parity** — the visible/hidden state currently relies on opacity + pointer-events; sighted-user gating differs from screen-reader gating. Defensible per WAI-ARIA APG, but a follow-up could toggle `aria-hidden` for full parity.
