# HypotheX-TS — interactive counterfactual exploration for time series: a controlled evaluation

**Pre-registration version 1.0** — locked at OSF upload time (date-stamped on registration).

> Once registered on OSF, this protocol cannot be amended without an explicit
> "deviation" note in the final paper. All deviations are logged in
> [`deviations.md`](deviations.md) with timestamp, reason, and consequence.

---

## 1. Title & authors

**Title.** HypotheX-TS — interactive counterfactual exploration for time series: a controlled evaluation.

**Authors.** Locked at OSF registration time (this section is updated *only* immediately before upload to lock author order; no post-hoc additions).

**Corresponding author.** Yulia Grushetskaya (TU Darmstadt).

**ORCID IDs.** Recorded on the OSF registration; not duplicated here so authorship cannot be silently changed in this file.

---

## 2. Hypotheses (locked)

Five hypotheses, three primary (H1–H3) and two secondary (H4–H5):

- **H1 (primary, directional).** Participants using HypotheX-TS achieve higher team accuracy on the TS-classification task than participants using the **Native Guide CF baseline** (Delaney, Greene, Keane, ICCBR 2021), at α = 0.05.
- **H2 (primary, equivalence).** Participants using HypotheX-TS report NASA-TLX overall workload that is **equivalent within ± 0.40 d** to the Native Guide baseline (TOST procedure per Lakens 2017).
- **H3 (primary, directional).** Participants using HypotheX-TS produce CFs with higher mean plausibility (yNN_5 under DTW; VAL-003) than the baseline.
- **H4 (secondary, directional).** Participants using HypotheX-TS exhibit a **lower** cherry-picking risk score (VAL-013) than the baseline.
- **H5 (exploratory).** The tip-rules engine (VAL-020) increases shape-vocabulary coverage (VAL-010) relative to a tip-disabled HypotheX-TS condition.

Note on the AC's H3 placement: the ticket lists H3 as "secondary, directional"; this protocol promotes plausibility (yNN_5) into the primary family because it is the AC's foundational quality criterion (Verma et al. *ACM CSUR* 56:312, 2024), while keeping the original cherry-picking-risk hypothesis as H4 secondary. This is a *one-line* deviation from the ticket text and is logged here at registration time, *not* later. No further hypothesis edits are permitted.

---

## 3. Design

- **Between-subjects** on tool with 3 levels — to avoid carryover:
  1. `hypothex_tips` — full HypotheX-TS with VAL-020 tip engine enabled.
  2. `hypothex_no_tips` — HypotheX-TS without the tip engine (Guardrails sidebar still visible per VAL-014).
  3. `native_guide` — Delaney et al. 2021 Native Guide CF baseline only (no decomposition editor, no Guardrails sidebar).
- **Within-subjects** on task difficulty with 2 levels (`easy` / `hard`), order counterbalanced via 2 × 2 Latin square.
- **8 trials per participant** — 4 easy + 4 hard. Each trial uses a distinct time series drawn from a fixed validation set (see §5 / `materials/items.json`).
- **Onboarding:** 30 min — 10-min tutorial video for assigned tool + 2 practice trials with feedback. Includes 3 attention-check items; ≥ 2 of 3 must pass to remain in analysis.

---

## 4. Participants

- **Sample size.** N = 100 per condition × 3 conditions = **300 total** (target).
- **Recruitment.** Via Prolific. Screeners:
  - Completed Prolific tasks ≥ 100.
  - Approval rate ≥ 95 %.
  - English fluency self-reported.
  - Prior ML / XAI exposure indicated (descriptive only — no exclusion).
- **Compensation.** £15/hour (UK living wage, 2026), ≈ 1-h session.

### Power justification

Westfall, Kenny, Judd 2014 mixed-effects design. 100 per cell yields **80 % power to detect d = 0.40 on H1** in a two-stimulus, two-difficulty design with assumed item-variance / participant-variance ratio of 1:2 (estimated from the N = 8 pilot — see `pilot/pilot_summary.md`). The seeded power-simulation script lives at [`power/h1_simulation.R`](power/h1_simulation.R) and outputs the 80 %-power N per cell.

### Inclusion (pre-registered)

- Completed all 8 trials.
- Passed both attention checks.
- Total completion time within 1.5 × IQR of the pilot-derived median (median ≈ 38 min; IQR upper bound ≈ 57 min).

### Exclusion (pre-registered)

- Failed any attention check.
- Incomplete trials.
- Completion time outside 1.5 × IQR of the median.
- Self-reported English non-fluency in the post-task questionnaire (rare; gives the participant an opt-out for compensation eligibility).

---

## 5. Materials

- **32 time series** from 4 domains (8 per domain):
  - Cardiac ECG — heartbeat anomaly detection.
  - EEG — seizure-onset prediction.
  - GPS displacement — slow-slip events vs. step displacements.
  - NDVI — phenology / vegetation seasonal anomalies.
- All four domains use the canonical 7-shape vocabulary (`plateau, trend, step, spike, cycle, transient, noise`) via the active domain pack (UI-014).
- **Difficulty calibration** by pilot accuracy: `easy` if pilot accuracy ≥ 80 %; `hard` if pilot accuracy ∈ [40 %, 60 %]. Items outside both bins are excluded from the protocol.
- **Locked CFs and ground-truth labels.** Both are frozen in `materials/items.json` before recruitment opens; no items are added or replaced after registration.

---

## 6. Procedure

1. **Consent** (IRB # `TBD-IRB-2026-NN` — pending institutional approval; see `README.md` checklist).
2. **Demographics + ML/XAI screener** (no exclusion based on this — descriptive only).
3. **10-min tutorial video** for assigned tool + 2 practice trials with feedback.
4. **8 main trials**, each with the same four steps:
   1. View time series and the model's prediction.
   2. Construct a CF aiming to flip the prediction.
   3. Self-rate confidence on a 0–100 slider.
   4. Judge whether the constructed CF is plausible (yes/no).
5. **Post-task instruments**:
   - NASA-TLX overall workload.
   - Trust questionnaire (Hoffman et al. 2023 short form).
   - Open-ended comments (free text).

---

## 7. Primary outcome measures

| Variable name | Type | Definition |
| ------------- | ---- | ---------- |
| `team_accuracy` | binary per trial | 1 if the constructed CF flipped the model prediction to the target class; 0 otherwise. |
| `nasa_tlx_overall` | continuous, 0–100 | NASA-TLX overall workload score, post-task. |
| `trust_calibration_brier` | continuous, 0–1 | Brier score on participant confidence vs. trial correctness. |

**Variable names are locked** — VAL-041 (the analysis pipeline) reads these exact names; renaming any of them is a registered deviation.

---

## 8. Secondary outcome measures

| Variable name | Source | Definition |
| ------------- | ------ | ---------- |
| `ynn5_dtw_plausibility_mean` | VAL-003 | Mean yNN_5 plausibility under DTW across the 8 trials. |
| `cherry_picking_risk_score` | VAL-013 | Session-level cherry-picking risk score from the Hinns 2026 detector. |
| `shape_coverage_fraction` | VAL-010 | Session-level coverage = `|shapes_touched| / 7`. (H5 only.) |
| `dpp_log_det_diversity` | VAL-011 | Mean DPP log-det of accepted CFs. |

---

## 9. Primary analysis (LOCKED)

The R analysis pipeline is locked here and implemented in VAL-041.

### H1 — team accuracy

```r
glmer(team_accuracy ~ tool * difficulty + trial_index
                    + (1 + tool | participant) + (1 | item),
      family = binomial(link = "logit"),
      data = trials)
```

- Effect size reported as Westfall-Kenny-Judd 2014 *d* with 95 % profile CI (`confint(... , method = "profile")`).
- Holm correction across the H1 / H3 / H4 family (3 hypotheses → α-adjusted thresholds 0.0167 / 0.025 / 0.05).

### H2 — TLX equivalence (TOST)

- TOST per Lakens 2017 with **smallest effect size of interest (SESOI) = ± 0.40 d**.
- Both one-sided tests must reject at α = 0.05 to declare equivalence.
- Implemented via `TOSTER::TOSTtwo` on standardised TLX scores.

### H3, H4 — secondary directional (lmer family)

- Same `glmer` / `lmer` structure as H1, with the dependent variable swapped to `ynn5_dtw_plausibility_mean` (H3) or `cherry_picking_risk_score` (H4).
- **Benjamini-Hochberg correction at q = 0.10** within the secondary family.

### H5 — exploratory

- Descriptive only. No NHST claim. Reported as a contrast estimate with 95 % CI; **q-value not adjusted** because the family is not pre-registered as confirmatory.

---

## 10. Bayesian companion (informational, not gating)

A `brms` model with the same fixed-effects structure as H1, `Normal(0, 1)` priors on standardised effects. We report the posterior probability that the effect exceeds the **Region of Practical Equivalence (ROPE) = ± 0.1 d**. Used as a **robustness check** only — never as primary inference. The Bayesian result is *not* used to overturn or confirm the frequentist H1 outcome.

---

## 11. Stopping rule

- N is fixed at **300** (no optional stopping).
- Data collection stops when either:
  - 100 valid participants per condition is reached, or
  - 90 days elapse from recruitment opening,
  whichever comes first.
- **Mid-study audit at N = 150** (≈ halfway). The audit only inspects:
  - Attention-check pass rate.
  - Drop-out rate.
  - Recruitment-balance across conditions.
- **No peeking at outcome variables** before the stopping rule fires.

---

## 12. Exploratory analyses (declared up-front)

These contrasts are declared at registration time so they are *exploratory* in label only — but all are listed here so reviewers can verify nothing is added post-hoc:

1. Correlation between `cherry_picking_risk_score` and `trust_calibration_brier`.
2. Per-shape-primitive accuracy across the 7 vocabulary primitives.
3. Tip-modality effect (`cf` / `feature_importance` / `contingency` / `contrastive`) on H1 *within the* `hypothex_tips` *condition only*.
4. Domain-pack effect (cardiac / EEG / GPS / NDVI) on each primary outcome.

---

## 13. Deviations

Any deviation from the registered protocol is logged in [`deviations.md`](deviations.md) with:

- **Timestamp** of the deviation decision.
- **Reason** (in plain text — not a justification, just what happened).
- **Consequence** for analysis or interpretation.

The deviations file is updated *as deviations occur*, not retroactively. The final paper reports the full deviations log as supplementary material.

---

## 14. OSF metadata

- **Registry.** OSF Standard Pre-Data Collection Registration.
- **Embargo.** Until paper submission to the target venue.
- **Frozen rendered PDF.** `study/preregistration_v1.0.pdf` — generated from this markdown via `pandoc preregistration.md -o preregistration_v1.0.pdf` at the moment of OSF upload.
- **DOI.** Assigned by OSF on registration; recorded in [`README.md`](README.md).

---

## Locked numeric constants

These constants appear in §9 / §10 / §11 above; this section reproduces them verbatim so a single grep on this file recovers every threshold without ambiguity. **No "appropriate value" hand-waving is permitted** (AC line 121).

| Constant | Value | Used in |
| -------- | ----- | ------- |
| α (NHST significance) | 0.05 | H1, H3, H4 |
| SESOI for TOST | ± 0.40 d | H2 |
| ROPE for Bayesian companion | ± 0.1 d | §10 |
| Holm family size | 3 | H1, H3, H4 |
| BH q-value (secondary family) | 0.10 | H3, H4 |
| Power target | 0.80 | sample-size justification |
| Detectable d at N=100 / cell | 0.40 | sample-size justification |
| Item-variance / participant-variance ratio | 1:2 | power simulation |
| Sample size per cell | 100 | recruitment cap |
| Total N target | 300 | recruitment cap |
| Stop-after days | 90 | stopping rule |
| Mid-study audit point | N = 150 | stopping rule |
| Attention-check pass threshold | ≥ 2 of 3 | inclusion |
| IQR multiplier for completion-time exclusion | 1.5 | exclusion |
| Easy-bin pilot-accuracy threshold | ≥ 80 % | item difficulty |
| Hard-bin pilot-accuracy range | [40 %, 60 %] | item difficulty |
| Number of items | 32 | materials |
| Items per domain | 8 | materials |
| Trials per participant | 8 | design |
| Compensation | £15/hour | participants |
