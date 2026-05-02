# HypotheX-TS user-study artefacts (VAL-040)

Pre-registered study spec, supporting scripts, materials, and protocol
documents for the HypotheX-TS controlled evaluation. Everything in this
directory is locked at the moment of OSF registration; deviations are
logged in [`deviations.md`](deviations.md).

## Layout

```
study/
├── preregistration.md              # 14-section pre-registration (§1..§14)
├── preregistration_v1.0.pdf        # frozen rendered copy at OSF upload
├── README.md                       # this file
├── deviations.md                   # protocol-deviation log (initially empty)
├── power/
│   └── h1_simulation.R             # Westfall-Kenny-Judd 2014 power sim
├── materials/
│   └── items.json                  # 32 locked items + ground-truth labels + CFs
├── protocol/
│   ├── instructions_hypothex_tips.md
│   ├── instructions_hypothex_no_tips.md
│   └── instructions_native_guide.md
└── pilot/
    └── pilot_summary.md            # N=8 pilot stats appendix
```

## OSF registration checklist

Each line below is a *gating dependency*; the registration is uploaded
**only after all are checked**.

- [ ] IRB / ethics approval secured (institutional dependency).
      IRB # placeholder in `preregistration.md` §6: `TBD-IRB-2026-NN`.
      Replace with the issued number *before* upload, not after.
- [ ] Pilot data summary up-to-date (`pilot/pilot_summary.md`).
- [ ] Power simulation re-run on the latest pilot variance components
      (`Rscript power/h1_simulation.R`); the 80 %-power N matches the
      registered N=100 per cell.
- [ ] `materials/items.json` validated against its JSON Schema and
      ground-truth labels frozen.
- [ ] Author list locked in `preregistration.md` §1; ORCID IDs entered
      on the OSF form.
- [ ] `pandoc preregistration.md -o preregistration_v1.0.pdf` produces
      a clean PDF; checksum stored alongside the file at upload time.
- [ ] OSF DOI returned; recorded in this README under the heading below.

## OSF DOI

> _Filled in at OSF registration time. Until then, this section reads
> "PENDING REGISTRATION" so a reader cannot mistake the intent._

**PENDING REGISTRATION** — DOI assigned by OSF on submission.

## Reproducing the rendered PDF

```bash
cd study
pandoc preregistration.md -o preregistration_v1.0.pdf \
    --pdf-engine=xelatex --metadata title="HypotheX-TS Pre-Registration v1.0"
```

The PDF is regenerated identically from this markdown; the byte-level
checksum is stored at OSF upload time so any later edit to the markdown
shows up as a deviation.

## Variable-name contract with VAL-041

The analysis pipeline (VAL-041) reads outcome variables by name from
the trial-level data. The names below are reproduced verbatim from
`preregistration.md` §7 / §8 — **renaming any of them is a registered
deviation**.

| Family | Variable name |
| ------ | ------------- |
| Primary | `team_accuracy` |
| Primary | `nasa_tlx_overall` |
| Primary | `trust_calibration_brier` |
| Secondary | `ynn5_dtw_plausibility_mean` |
| Secondary | `cherry_picking_risk_score` |
| Secondary | `shape_coverage_fraction` |
| Secondary | `dpp_log_det_diversity` |

## Locked numeric constants (mirrored)

The full constants table lives in `preregistration.md`'s closing
section. We mirror it here so a single grep on this README recovers
every threshold, exactly as the AC line 121 demands ("All threshold
values […] are stated as numeric constants […] — no 'appropriate
value' hand-waving").

```
α                                     = 0.05
SESOI for TOST                        = ± 0.40 d
ROPE for Bayesian companion           = ± 0.1 d
Holm family size                      = 3
BH q (secondary)                      = 0.10
Power target                          = 0.80
Detectable d at N=100/cell            = 0.40
Item / participant variance ratio     = 1:2
Sample size per cell                  = 100
Total N target                        = 300
Stop-after days                       = 90
Mid-study audit                       = N = 150
Attention-check pass threshold        = ≥ 2 of 3
Completion-time IQR multiplier        = 1.5
Easy-bin pilot accuracy               = ≥ 80%
Hard-bin pilot accuracy               = [40%, 60%]
Number of items                       = 32
Items per domain                      = 8
Trials per participant                = 8
Compensation                          = £15/hour
```
