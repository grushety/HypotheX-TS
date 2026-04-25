# VAL-040 — Pre-registered user-study spec on OSF

**Status:** [ ] Done
**Depends on:** VAL-001..014 + VAL-020 (full validation pipeline live and stable); UI-001..018 (full UI in place); pilot data from N=8 internal testers

---

## Goal

Author the **pre-registered user-study spec** for the HypotheX-TS evaluation, formatted for direct upload to the **Open Science Framework (OSF) registries** before any data is collected. Lock hypotheses, design, sample size, exclusion criteria, primary analysis, equivalence bounds, and planned-vs-exploratory contrasts. Once registered, the protocol cannot be amended without an explicit "deviation" note in the final paper.

**Why:** Per [[HypotheX-TS - Statistical Validation SOTA]] §C.6, pre-registration is **weak in TS-XAI** (Rong et al. TPAMI 2024 documents this). Adopting it is a *methodological contribution by virtue of doing it*, and prevents reviewer pushback on HARKing (Hypothesizing After Results are Known). It also constrains the analysis pipeline (VAL-041) so we cannot p-hack post-hoc.

**How it fits:** Deliverable is `study/preregistration.md` in the repo and a frozen-PDF copy at `study/preregistration_v1.0.pdf` plus an OSF DOI. VAL-041 implements the analysis pipeline locked here; deviations (if any) are documented in `study/deviations.md`.

---

## Methodological references (for `methodology-auditor`)

- Cockburn, Gutwin, Dix, **"HARK No More: On the Preregistration of CHI Experiments,"** *CHI 2018*, DOI 10.1145/3173574.3173715 (canonical pre-registration framework for HCI).
- Lakens, **"Equivalence Tests: A Practical Primer,"** *Social Psychological and Personality Science* 8:355–362 (2017), DOI 10.1177/1948550617697177 (TOST procedure).
- Kay, Nelson, Hekler, **"Researcher-Centered Design of Statistics,"** *CHI 2016*, DOI 10.1145/2858036.2858465 (Bayesian-companion design).
- Westfall, Kenny, Judd, **"Statistical Power and Optimal Design in Experiments in Which Samples of Participants Respond to Samples of Stimuli,"** *Journal of Experimental Psychology: General* 143:2020–2045 (2014), DOI 10.1037/xge0000014 (mixed-effects power analysis).
- Lazar, Feng, Hochheiser, **"Research Methods in Human-Computer Interaction,"** Morgan Kaufmann 3rd ed. 2024, ISBN 978-0-128-21536-7 (sample-size + recruitment standards).
- Rong et al., **"Towards Human-Centered Explainable AI: A Survey of User Studies for Model Explanations,"** *IEEE TPAMI* 46:2104–2122 (2024), DOI 10.1109/TPAMI.2023.3331846 (XAI user-study standards; explicit pre-registration recommendation).
- Nauta et al., **"From Anecdotal Evidence to Quantitative Evaluation Methods (Co-12),"** *ACM Computing Surveys* 55:295 (2023), DOI 10.1145/3583558 (XAI evaluation rubric — selects which Co-12 properties are tested).
- Buçinca, Lin, Gajos, Glassman, **"Proxy tasks and subjective measures can be misleading,"** *IUI 2020*, DOI 10.1145/3377325.3377498 (motivates objective task-performance primary outcome).
- Liao, Pribić, Han, Miller, Sow, **"Question-Driven Design Process for Explainable AI User Experiences,"** arXiv 2104.03483 (question-driven design of explanation features).

For the trust-calibration outcome:
- Hoffman, Mueller, Klein, Litman, **"Metrics for Explainable AI,"** *Frontiers in Computer Science* 5:1096257 (2023), DOI 10.3389/fcomp.2023.1096257.
- Zhang, Liao, Bellamy, **"Effect of Confidence and Explanation on Accuracy and Trust Calibration,"** *FAT\* 2020*, DOI 10.1145/3351095.3372852.

---

## Pre-registration spec — content of `study/preregistration.md`

### 1. Title & authors
HypotheX-TS — interactive counterfactual exploration for time series: a controlled evaluation. (Authors locked at registration time.)

### 2. Hypotheses (locked)
- **H1 (primary, directional):** participants using HypotheX-TS achieve higher team accuracy on a TS-classification task than participants using the **Native Guide CF baseline** (Delaney et al. 2021), at α = 0.05.
- **H2 (primary, equivalence):** participants using HypotheX-TS report NASA-TLX overall workload that is *equivalent within ± 0.40 d* to the Native Guide baseline (TOST per Lakens 2017).
- **H3 (secondary, directional):** participants using HypotheX-TS produce CFs with higher mean plausibility (yNN_5 under DTW) than the baseline.
- **H4 (secondary, directional):** participants using HypotheX-TS exhibit a lower cherry-picking risk score (VAL-013) than the baseline.
- **H5 (exploratory):** the tip-rules engine (VAL-020) increases shape-vocabulary coverage relative to a tip-disabled HypotheX-TS condition.

### 3. Design
- **Between-subjects** on tool (3 levels: HypotheX-TS-with-tips, HypotheX-TS-no-tips, Native Guide baseline) to avoid carryover.
- **Within-subjects** on task difficulty (2 levels: easy / hard) with order counterbalanced via 2 × 2 Latin square.
- 8 trials per participant (4 easy + 4 hard); each trial uses a distinct time series drawn from a fixed validation set.
- 30-min onboarding + practice with attention checks (≥ 2 of 3 must pass).

### 4. Participants
- N = 100 per condition × 3 conditions = 300 total (target). Recruited via Prolific with screening: completed-tasks ≥ 100, approval ≥ 95 %, English-fluent, prior ML/XAI exposure indicated. Compensated at £15/hour (UK living wage), ≈ 1-h session.
- **Power justification (Westfall et al. 2014):** 100/cell yields 80 % power to detect *d = 0.40* on H1 in a two-stimulus, two-difficulty mixed-effects design with assumed item-variance / participant-variance ratio of 1:2 (estimated from pilot). Power simulation script at `study/power/h1_simulation.R`, seeded RNG.
- **Inclusion:** completed all 8 trials, passed both attention checks, completion time within 1.5 × IQR of the median.
- **Exclusion (pre-registered):** failed attention check (any), incomplete trials, completion-time outside 1.5 × IQR, self-reported English non-fluency.

### 5. Materials
- 32 time series drawn from 4 domains (8 each): cardiac ECG (heartbeat anomaly), EEG (seizure onset), GPS displacement (slow-slip vs. step), NDVI (phenology). All four domains use shape vocabulary {plateau, trend, step, spike, cycle, transient, noise} via the active domain pack (UI-014).
- Difficulty calibrated by pilot accuracy: easy = pilot accuracy ≥ 80 %, hard = pilot accuracy ∈ [40 %, 60 %].
- Ground-truth labels and CFs locked before recruitment.

### 6. Procedure
1. Consent (IRB #TBD).
2. Demographics + ML/XAI screener (no exclusion based on this — descriptive only).
3. 10-min tutorial video for assigned tool + 2 practice trials with feedback.
4. 8 main trials, each: (i) view series and model prediction, (ii) construct a CF aiming to flip the prediction, (iii) self-rate confidence, (iv) judge whether the CF is plausible.
5. Post-task NASA-TLX, trust questionnaire (Hoffman 2023 short form), open-ended comments.

### 7. Primary outcome measures
- **Team accuracy** (binary per trial): did the constructed CF actually flip the model? Aggregated as logit-mixed-effects.
- **NASA-TLX overall** (continuous, 0–100).
- **Trust calibration** (Brier score on confidence vs. correctness).

### 8. Secondary outcomes
- Mean yNN_5 plausibility under DTW (per VAL-003).
- Cherry-picking risk score (VAL-013).
- Shape-vocabulary coverage (VAL-010; H5 only).
- Mean DPP log-det of accepted CFs (VAL-011).

### 9. Primary analysis (LOCKED)
- **H1:** `lmer(accuracy ~ tool*difficulty + trial_index + (1+tool|participant) + (1|item))` (binomial via `glmer` with logit link). Report Westfall-Kenny-Judd 2014 d with 95 % profile CI. Holm correction across H1 / H3 / H4 family.
- **H2 (equivalence):** TOST on TLX with SESOI = ± 0.40 d (Lakens 2017). Reject H2-null if both one-sided tests p < 0.05.
- **H3, H4:** same lmer family as H1, BH at q = 0.10 within secondary family.
- **H5 (exploratory):** descriptive only; no NHST claim.

### 10. Bayesian companion (informational, not gating)
`brms` model with same fixed-effects structure as H1, Normal(0, 1) priors on standardised effects. Report posterior probability that effect exceeds ROPE = ± 0.1 d. Used as a robustness check only, not as primary inference.

### 11. Stopping rule
N is fixed at 300 (no optional stopping). Data collection stops when 100 valid participants per condition is reached or 90 days elapse (whichever first). Mid-study audit at N = 150 only checks data integrity (attention-check pass rate, drop-out rate); no peeking at outcome variables.

### 12. Exploratory analyses (declared)
- Correlation between cherry-picking risk and trust calibration.
- Per-shape-primitive accuracy.
- Tip-modality effect (CF vs. contrastive vs. contingency) on H1 within HypotheX-TS-with-tips condition.

### 13. Deviations
Any deviation from the registered protocol logged in `study/deviations.md` with timestamp, reason, and consequence; reported in the paper.

### 14. OSF metadata
- Registry: OSF Standard Pre-Data Collection Registration.
- Embargo: until paper submission.
- Frozen PDF: `study/preregistration_v1.0.pdf`.
- DOI: assigned by OSF on registration.

---

## Acceptance Criteria

- [ ] `study/preregistration.md` in the repo containing all 14 sections above with **all numbers locked** (not "TBD" except IRB # which depends on institution timing)
- [ ] `study/preregistration_v1.0.pdf` — frozen rendered PDF at the moment of OSF upload
- [ ] OSF registration created (link recorded in `study/README.md`); registration timestamp predates first participant onboarding
- [ ] `study/power/h1_simulation.R` — seeded power simulation script implementing Westfall-Kenny-Judd 2014 mixed-effects design, with pilot-data-derived variance components; output is the 80 %-power N per cell
- [ ] `study/materials/items.json` — locked list of 32 time series with metadata (domain, difficulty bin, ground-truth label, locked CF)
- [ ] `study/protocol/instructions_*.pdf` — instructions for each condition, frozen
- [ ] `study/deviations.md` exists (initially empty placeholder)
- [ ] All primary and secondary outcome variable names match exactly the variable names that VAL-041 will use
- [ ] All threshold values (SESOI = ± 0.40 d, ROPE = ± 0.1 d, BH q = 0.10, Holm family) are stated as numeric constants in the markdown — no "appropriate value" hand-waving
- [ ] IRB / ethics approval secured before OSF upload (institutional dependency — flagged in checklist)
- [ ] Pilot data (N = 8 internal testers) used to calibrate difficulty bins is reported in an appendix

## Definition of Done
- [ ] Run `methodology-auditor` agent with the paper references above. Confirm:
  - Hypotheses are pre-stated, directional (or equivalence), and falsifiable
  - Sample size is justified by a *a priori* power simulation (not retrospective)
  - Exclusion criteria are pre-registered, not data-dependent
  - Primary analysis is locked — exact formula, exact correction, exact α
  - TOST equivalence bound (Lakens 2017) is stated as a SESOI in d-units, not p > 0.05
  - Bayesian companion is informational, not gating (Kay 2016 design)
  - Deviation logging procedure is in place
  - All XAI Co-12 properties tested are explicit (Nauta 2023)
  - The protocol does not test proxy tasks where the primary outcome should be objective task performance (Buçinca 2020)
- [ ] Run `code-reviewer` agent — no blocking issues with the power-simulation R code; seed reproducibility verified
- [ ] OSF link recorded in `study/README.md` with timestamp
- [ ] `git tag preregistration-v1.0`; `git commit -m "VAL-040: pre-registered user-study spec v1.0 (locked)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
