# Data dictionary — VAL-041 analysis pipeline

Variable names below match `study/preregistration.md` §7-§8 and
`study/analysis/_constants.R::ALL_OUTCOMES` exactly. **Renaming any
of them is a registered deviation** logged in `study/deviations.md`.

## Layout

```
study/data/
├── raw/                  # exported from the study platform; immutable
│   ├── trials.rds        # one row per (participant, trial)
│   └── participants.rds  # one row per participant (post-task instruments)
├── processed/            # produced by 00-make-processed-data.R
│   ├── study.rds         # post-exclusions analysis-ready trial frame
│   └── exclusion_audit.csv
├── synthetic.rds         # produced by make_synthetic.R for CI smoke
└── README.md             # this file
```

`raw/` is **immutable** — the analysis pipeline never writes there. The
upstream study platform (Prolific export → cleaning script outside
this repo) populates it once at study-end.

## Trial-level fields (`trials.rds` / `synthetic.rds`)

| Variable | Type | Description |
| -------- | ---- | ----------- |
| `participant` | factor | Stable participant ID. |
| `tool` | factor | One of `native_guide` / `hypothex_no_tips` / `hypothex_tips`. Reference level: `native_guide`. |
| `item` | factor | Time-series item ID; matches an entry in `study/materials/items.json`. |
| `domain_pack` | factor | One of `cardiac_ecg` / `eeg` / `gps_displacement` / `ndvi_phenology`. |
| `difficulty` | factor | `easy` / `hard`. |
| `trial_index` | integer | 1..8 within participant; presentation order. |
| `shape_primitive` | factor | One of the 7 shape primitives that the item's CF targets. |
| `team_accuracy` | binary | 1 if the constructed CF flipped the model to the target class. **Primary outcome.** |
| `confidence` | numeric (0–100) | Participant-rated confidence on the constructed CF. |
| `tip_modality` | factor or NA | One of `cf` / `feature_importance` / `contingency` / `contrastive` for the dominant tip emitted on the trial; `NA` outside `hypothex_tips`. |
| `nasa_tlx_overall` | numeric (0–100) | Post-task NASA-TLX overall workload (one value per participant; carried on every trial row for `lmer` convenience). **Primary outcome.** |
| `trust_calibration_brier` | numeric (0–1) | Per-participant Brier score from `05-trust-calibration-brier.R`; carried on every trial row. **Primary outcome.** |
| `ynn5_dtw_plausibility_mean` | numeric (0–1) | Per-trial yNN_5 plausibility under DTW (VAL-003). **Secondary outcome.** |
| `cherry_picking_risk_score` | numeric (0–1) | Per-participant cherry-picking risk score (VAL-013); carried on every trial row. **Secondary outcome.** |
| `shape_coverage_fraction` | numeric (0–1) | Per-participant `|shapes_touched| / 7` (VAL-010); carried on every trial row. **Secondary outcome.** |
| `dpp_log_det_diversity` | numeric | Per-participant DPP log-det of accepted CFs (VAL-011); carried on every trial row. **Secondary outcome.** |

## Participant-level fields (`participants.rds`)

| Variable | Type | Description |
| -------- | ---- | ----------- |
| `participant` | factor | Same ID as in `trials.rds`. |
| `tool` | factor | Tool condition. |
| `attention_check_pass_count` | integer (0–3) | Number of attention checks passed. Inclusion threshold: ≥ 2 (VAL-040 §4). |
| `completion_time_min` | numeric | Total session time in minutes; used for IQR exclusion (VAL-040 §4). |
| `english_fluent_self_report` | logical | Self-reported English fluency on the post-task questionnaire. |
| `nasa_tlx_overall` | numeric | One row per participant; the trial-level join is a convenience copy. |
| `cherry_picking_risk_score` | numeric | One row per participant. |
| `shape_coverage_fraction` | numeric | One row per participant. |
| `dpp_log_det_diversity` | numeric | One row per participant. |
| `trust_calibration_brier` | numeric | One row per participant. |

## Notes

- **No raw signal data is committed to this directory.** Time-series
  series_paths in `materials/items.json` point to a separate, larger
  data tree (released separately as a Zenodo deposit alongside the
  paper).
- **Synthetic dataset** (`synthetic.rds`) is the CI smoke fixture; its
  ground-truth effects are documented in `analysis/make_synthetic.R`.
- Outcome variable names are duplicated in three places — this file,
  `_constants.R::ALL_OUTCOMES`, and `preregistration.md` §7/§8. The
  Python invariant test pins all three.
