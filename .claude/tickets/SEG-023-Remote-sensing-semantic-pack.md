# SEG-023 — Semantic-layer domain pack: remote-sensing

**Status:** [ ] Done
**Depends on:** SEG-014 (STL/MSTL), SEG-015 (BFAST), SEG-017 (LandTrendr); [[HypotheX-TS - Label Vocabulary Research]]

---

## Goal

Seed a remote-sensing & phenology domain pack: `greenup, senescence, peak_of_season, dormancy, disturbance, recovery, wet_up, dry_down, heatwave, coldwave, cloud_gap, APS, seasonal_deformation, linear_deformation`.

**Why:** Remote-sensing scientists reason in phenology and disturbance-recovery cycles; SAR operators reason in APS and deformation. Translating shape segments into this vocabulary is a prerequisite for the UI-005 palette to feel domain-native.

**How it fits:** Loaded by UI-014 when active domain = remote-sensing. Detectors wire to SEG-014 (STL/MSTL for phenology cycles), SEG-015 (BFAST for disturbance breakpoints), SEG-017 (LandTrendr for trajectory segmentation).

---

## Paper references (for `algorithm-auditor`)

- Jönsson & Eklundh (2002, 2004) "TIMESAT — a program for analyzing time-series of satellite sensor data" — *Computers & Geosciences* 30:833–845 (SOS/EOS, peak of season).
- Verbesselt, Hyndman, Newnham, Culvenor (2010) — BFAST (disturbance).
- Kennedy, Yang, Cohen (2010) — LandTrendr (recovery).
- Yunjun, Fattahi, Amelung (2019) "Small baseline InSAR time series analysis: Unwrapping error correction and noise reduction" — *CAGEO* 133:104331 (APS, GACOS).
- Zebker & Villasenor (1992) "Decorrelation in interferometric radar echoes" — *IEEE TGRS* 30(5):950 (InSAR coherence).

---

## Pack schema (YAML)

```yaml
name: remote-sensing
version: 1.0
semantic_labels:
  greenup:
    shape_primitive: trend
    context_predicate: "slope > 0 during spring_window"
    detector: timesat_threshold
    detector_params: {threshold_percent: 20, window: spring}
  senescence:
    shape_primitive: trend
    context_predicate: "slope < 0 during autumn_window"
    detector: timesat_threshold
    detector_params: {threshold_percent: 80, window: autumn}
  peak_of_season:
    shape_primitive: plateau
    context_predicate: "amplitude > 0.9 * annual_max for short window"
    detector: mstl_peak_window
  dormancy:
    shape_primitive: plateau
    context_predicate: "amplitude < 0.2 * annual_max for extended period"
    detector: low_amplitude_plus_duration
  disturbance:
    shape_primitive: step
    context_predicate: "negative_step_magnitude > disturbance_threshold"
    detector: bfast_breakpoint
    detector_params: {magnitude_threshold: -0.2}
  recovery:
    shape_primitive: trend
    context_predicate: "positive_slope following disturbance"
    detector: landtrendr_positive_slope_post_disturbance
    detector_params: {min_recovery_slope: 0.05}
  wet_up:
    shape_primitive: trend
    context_predicate: "positive slope on SM index after dry_down"
    detector: slope_plus_context
  dry_down:
    shape_primitive: trend
    context_predicate: "negative slope on SM index after wet_up"
    detector: slope_plus_context
  heatwave:
    shape_primitive: transient
    context_predicate: "LST above 95th percentile for >= 3 days"
    detector: percentile_threshold_plus_duration
  coldwave:
    shape_primitive: transient
    context_predicate: "LST below 5th percentile for >= 3 days"
    detector: percentile_threshold_plus_duration
  cloud_gap:
    shape_primitive: noise
    context_predicate: "missingness_mask_value"
    detector: missingness_mask
  APS:
    shape_primitive: noise
    context_predicate: "spatial_atmospheric_correlation in InSAR stack"
    detector: gacos_correction_residual
  seasonal_deformation:
    shape_primitive: cycle
    context_predicate: "InSAR displacement with annual period"
    detector: mstl_annual_component
  linear_deformation:
    shape_primitive: trend
    context_predicate: "InSAR mean velocity > velocity_threshold"
    detector: etm_linear_rate
```

---

## Acceptance Criteria

- [ ] `backend/app/services/semantic_packs/remote_sensing.yaml` per schema
- [ ] Loadable via SEG-021 `load_pack('remote-sensing')`
- [ ] Covers phenology (greenup/peak/senescence/dormancy), disturbance/recovery, phenological transients (heatwave/coldwave), cloud_gap, APS, InSAR deformation
- [ ] Detectors wire to SEG-014 (STL/MSTL annual), SEG-015 (BFAST breakpoints), SEG-017 (LandTrendr post-disturbance slope)
- [ ] `timesat_threshold` detector implements SOS/EOS definitions per Jönsson 2004 Table 1 (20 % and 80 % amplitude thresholds default)
- [ ] `cloud_gap` detector reads missingness mask from data loader (no NaN interpolation before detection)
- [ ] `seasonal_deformation` reads from MSTL annual component only when period ≈ 365 ± 30 days
- [ ] Tests cover: pack loads; NDVI fixture with known SOS/EOS → labels attached; BFAST disturbance on synthetic fixture → `disturbance` label; InSAR fixture with annual period → `seasonal_deformation`
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper references: Jönsson 2004 (phenology thresholds), Verbesselt 2010 (BFAST), Kennedy 2010 (LandTrendr), Yunjun 2019 (APS). Confirm thresholds match paper recommendations and are parameterized (not hardcoded)
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "SEG-023: remote-sensing semantic pack (phenology, disturbance, InSAR)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
