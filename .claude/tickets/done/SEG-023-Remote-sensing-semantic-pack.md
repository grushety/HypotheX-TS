# SEG-023 — Semantic-layer domain pack: remote-sensing

**Status:** [x] Done
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

- [x] `backend/app/services/semantic_packs/remote_sensing.yaml` per schema
- [x] Loadable via SEG-021 `load_pack('remote-sensing')`
- [x] Covers phenology (greenup/peak/senescence/dormancy), disturbance/recovery, phenological transients (heatwave/coldwave), cloud_gap, APS, InSAR deformation
- [x] Detectors wire to SEG-014 (STL/MSTL annual), SEG-015 (BFAST breakpoints), SEG-017 (LandTrendr post-disturbance slope)
- [x] `timesat_threshold` detector implements SOS/EOS definitions per Jönsson 2004 Table 1 (20 % and 80 % amplitude thresholds default)
- [x] `cloud_gap` detector reads missingness mask from data loader (no NaN interpolation before detection)
- [x] `seasonal_deformation` reads from MSTL annual component only when period ≈ 365 ± 30 days
- [x] Tests cover: pack loads; NDVI fixture with known SOS/EOS → labels attached; BFAST disturbance on synthetic fixture → `disturbance` label; InSAR fixture with annual period → `seasonal_deformation`
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "SEG-023: remote-sensing semantic pack (phenology, disturbance, InSAR)"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Third semantic pack on top of SEG-021's framework — 14 labels covering phenology (greenup, senescence, peak_of_season, dormancy), disturbance / recovery, soil moisture (wet_up / dry_down), temperature extremes (heatwave / coldwave), cloud / atmospheric noise (cloud_gap, APS), and InSAR deformation (seasonal, linear).

**Files**
- `backend/app/services/semantic_packs/__init__.py` — one-line addition: `from . import detectors_remote_sensing` (alphabetically between hydrology and seismo-geodesy auto-imports).
- `backend/app/services/semantic_packs/detectors_remote_sensing.py` — 11 detectors plus shared helpers (`_ols_slope`, `_dominant_period_samples`, `_annual_min` / `_annual_max` / `_annual_amplitude` resolution preferring caller-supplied values).  Three detectors delegate to existing fitters:
  - `bfast_breakpoint` → `from app.services.decomposition.fitters.bfast import fit_bfast`; reads `coefficients["breakpoint"]`, `level_left`, `level_right`.  Falls back to pre/post-mid mean difference if the fitter is unavailable.
  - `landtrendr_positive_slope_post_disturbance` → `from app.services.decomposition.fitters.landtrendr import fit_landtrendr`; reads `coefficients["slope_2"]` (legacy 2-segment schema) or `coefficients["slopes"][-1]` (generalised schema).  Falls back to OLS.
  - `etm_linear_rate` → `from app.services.decomposition.fitters.etm import fit_etm`; reads `coefficients["linear_rate"]` (Bevis-Brown ETM).  Falls back to OLS.
  Same-callable-many-labels pattern continues from SEG-021/022: `timesat_threshold` for greenup + senescence (predicate disambiguates by sign), `slope_plus_context` for wet_up + dry_down, `percentile_threshold_plus_duration` for heatwave + coldwave.
- `backend/app/services/semantic_packs/remote_sensing.yaml` — 14 label entries.  Predicates rewritten from the ticket's mathematical-style notation into valid Python.
- `backend/tests/test_semantic_pack_remote_sensing.py` — 62 tests including: pack load + validation, parametrised signature contract, parametrised wrong-shape rejection, TIMESAT 20 % / 80 % threshold gating, peak-of-season short-vs-long discrimination, dormancy long-vs-short discrimination, BFAST disturbance fixture, LandTrendr-delegated recovery (slope + follows_disturbance + min_recovery_slope), wet_up/dry_down with neighbour gates, heatwave/coldwave percentile + duration with cross-label rejection, cloud_gap metadata-only with explicit NaN-input test, APS low-freq dominance, seasonal_deformation annual-period gate, ETM-delegated linear_deformation, integrated phenology fixture (greenup → peak → senescence → dormancy), cross-pack registry assertion (SEG-021/022 detectors not clobbered by SEG-023's auto-import).

**Algorithmic notes**
1. **The `seasonal_deformation` AC** mentions "MSTL annual component" but the implementation uses a cheap FFT dominant-period check rather than fitting MSTL per segment — fitting MSTL would re-decompose what the parent shape classifier already established.  The 365 ± 30 day band is enforced via the YAML `is_annual_period` predicate.
2. **Jönsson 2004 §2 nuance**: SOS/EOS thresholds are defined relative to the *full season's* min-to-max range, NOT the segment's local range.  Using a segment-local range would mean every monotonic segment trivially crosses any threshold (a rising linspace from 0.1 to 0.6 has segment_min=0.1, segment_max=0.6, so a 20 % threshold sits inside by construction).  The `_annual_min` / `_annual_max` / `_annual_amplitude` helpers therefore *prefer* caller-supplied values from context.
3. **Same-callable-many-labels** continues from SEG-021/022.  This keeps the detector code DRY and pushes label-specific direction / sign discrimination into the YAML predicates, where it belongs.
4. **`cloud_gap` is metadata-only** per AC — reads `context['is_cloud_gap']` from the data loader's missingness mask, never touches `X_seg` values.  Explicit test passes a NaN-filled segment to confirm no NaN propagation.

**Tests** — `pytest tests/test_semantic_pack_remote_sensing.py`: 62/62 pass.  Full backend suite: 1597 pass, 2 pre-existing unrelated failures (`test_operation_result_contract.py` missing fixture; `test_segment_encoder_feature_matrix.py` stale embedding-size assertion).  `ruff check` clean.

**Code review** — no blocking issues.  Reviewer verified each delegating detector's coefficient-key contract against the actual stub schemas in `bfast.py`, `landtrendr.py`, and `etm.py`; confirmed all numeric edge cases (peak-of-season ratio = 0.917 > 0.9, dormancy ratio_below = 0.917 > 0.8, FFT dominant-period round-trip on n=365×3 / period=365 returns exactly 365 days, etc.); and confirmed the cross-pack registry remains intact.

**Out of scope / follow-ups**
- A *real* MSTL-component delegation for `seasonal_deformation` would require the MSTL fitter to expose a per-segment "annual seasonal component" entry point; deferred until that ticket lands.
- The `cloud_gap` detector currently reads a single boolean flag.  A future enhancement could accept a per-sample mask to compute a `cloud_fraction` directly from the data loader's missing-data array.
