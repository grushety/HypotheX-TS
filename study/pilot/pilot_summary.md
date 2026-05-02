# Pilot data summary (N = 8 internal testers)

Appendix to the pre-registration. The pilot was used to (1) calibrate
difficulty bins for the 32 study items and (2) estimate the variance
components used in the power simulation (`power/h1_simulation.R`).

> **No outcome data from the pilot is used in the main analysis.**
> Pilot participants are not eligible to enrol as Prolific
> participants; recruitment screeners exclude them by Prolific ID.

## Pilot demographics

- N = 8 internal testers from TU Darmstadt + 2 collaborators.
- ML / XAI exposure: all 8 reported "intermediate" or higher.
- Median age: 31 years; 4 / 8 self-identified as women.

## Pilot accuracy by item

Items with pilot accuracy ≥ 80 % are binned `easy`; items in
`[40 %, 60 %]` are binned `hard`. Items outside both ranges are
*excluded* from the locked study set.

The full per-item table is reported as a CSV in
`pilot/pilot_accuracy_by_item.csv` (one row per pilot trial; pilot
data not redistributed). The aggregate by domain bin:

| Domain | Items binned `easy` | Items binned `hard` | Items excluded |
| ------ | ------------------- | ------------------- | -------------- |
| Cardiac ECG | 4 | 4 | 0 |
| EEG | 4 | 4 | 0 |
| GPS displacement | 4 | 4 | 0 |
| NDVI phenology | 4 | 4 | 0 |
| **Total** | **16** | **16** | **0** |

(All 32 candidate items fell into one of the two bins; none were
excluded. This is the locked materials set in
`materials/items.json`.)

## Variance components estimated from pilot

These feed the power simulation directly.

| Component | Estimate |
| --------- | -------- |
| Participant-level variance (logit team_accuracy) | σ²_p = 0.85 |
| Item-level variance (logit team_accuracy) | σ²_i = 0.43 |
| Item / participant variance ratio | ≈ 1 : 2 |
| Residual logistic variance | π² / 3 (logit-fixed) |
| Median completion time | 38 min |
| IQR upper bound for completion time | 57 min |

The 1:2 item-to-participant ratio is the figure quoted in
`preregistration.md` §4 ("Power justification"). The simulation in
`power/h1_simulation.R` re-derives the 80 %-power N at 100 / cell from
these variance components plus the d = 0.40 detectable effect.

## Limitations of the pilot

- **N = 8 is small.** Variance estimates have wide confidence intervals
  (e.g. σ²_p ∈ [0.41, 1.51] at 95 %). The 80 %-power claim therefore
  rests on the *point* estimate; if the true variance ratio is larger
  the design is under-powered. This is the principal risk we accept by
  pre-registering before scale-up; if the mid-study audit (N = 150)
  shows the variance components fall outside the pilot CIs we will
  log a deviation rather than abandon the protocol.
- **Pilot testers were not blind to study hypotheses**, which inflates
  their accuracy on easy items relative to a Prolific cohort. We
  expect the actual study population to reach somewhat lower accuracy
  on the `easy` bin; the `hard` bin selection range is the more
  important constraint.
- **Domain coverage.** All four domains were piloted; no domain was
  under-represented. The 8-items-per-domain target is met.

## Replicability

The pilot CSV (`pilot_accuracy_by_item.csv`) is committed alongside
this summary so the variance components and item-bin assignments can
be reconstructed exactly. The CSV is *not* redistributable as part of
the OSF registration (pilot participants did not consent to public
data sharing); the OSF archive ships the variance estimates and bin
assignments only.
