# SEG-022 — Semantic-layer domain pack: seismo-geodesy

**Status:** [ ] Done
**Depends on:** SEG-013 (ETM), SEG-018 (GrAtSiD); [[HypotheX-TS - Label Vocabulary Research]]

---

## Goal

Seed a seismology & geodesy domain pack: `P_arrival, S_arrival, coda, surface_waves, coseismic_offset, postseismic_relaxation, interseismic_loading, SSE, seasonal_signal, common_mode_error, tropospheric_delay, unwrapping_error, antenna_offset`.

**Why:** Seismic and geodetic scientists reason in these terms, not in shape primitives. Attaching them enables UI-005 to label palette buttons as "De-jump coseismic offset" or "Extend SSE duration" rather than abstract op names.

**How it fits:** Loaded by UI-014 when active domain = seismo-geodesy. Detectors wire to SEG-013 (ETM) and SEG-018 (GrAtSiD) so no duplicate parametric fitting; pack adds semantic interpretation on top.

---

## Paper references (for `algorithm-auditor`)

- Allen (1978) "Automatic earthquake recognition and timing from single traces" — *BSSA* 68(5):1521–1532 (STA/LTA).
- Savage (1983) "A dislocation model of strain accumulation and release at a subduction zone" — *JGR* 88(B6):4984–4996 (interseismic).
- Bevis & Brown (2014) — ETM.
- Bedford & Bevis (2018) — GrAtSiD (transient features, SSE).
- Hooper, Bekaert, Spaans, Arıkan (2012) "Recent advances in SAR interferometry time series analysis for measuring crustal deformation" — *Tectonophysics* 514:1–13 (APS, phase closure).
- Ansari, De Zan, Bamler (2018) "Efficient phase estimation for interferogram stacks" — *IEEE TGRS* 56:4109 (triplet closure).

---

## Pack schema (YAML)

```yaml
name: seismo-geodesy
version: 1.0
semantic_labels:
  P_arrival:
    shape_primitive: step
    detector: sta_lta
    detector_params: {window_sta_seconds: 1.0, window_lta_seconds: 10.0, threshold: 4.0}
  S_arrival:
    shape_primitive: step
    detector: sta_lta_with_polarization
  coda:
    shape_primitive: transient
    detector: post_S_envelope_fit
  surface_waves:
    shape_primitive: cycle
    detector: dispersive_wave_detection
  tremor:
    shape_primitive: noise
    context_predicate: "low_frequency_amplitude > threshold and sustained_minutes"
    detector: envelope_correlation_plus_lfe
  coseismic_offset:
    shape_primitive: step
    context_predicate: "step_magnitude > detection_threshold and origin_time_known"
    detector: etm_step_from_known_origin
  postseismic_relaxation:
    shape_primitive: transient
    context_predicate: "follows(coseismic_offset) and basis in {log, exp}"
    detector: fit_log_or_exp
    detector_params: {tau_range_days: [1, 1000]}
  interseismic_loading:
    shape_primitive: trend
    context_predicate: "excludes(coseismic_offset) and excludes(postseismic_relaxation)"
    detector: etm_linear_rate_ex_steps_ex_transients
  SSE:
    shape_primitive: transient
    context_predicate: "duration_days in [7, 365] and smooth_onset and smooth_decay"
    detector: gratsid_bump
    detector_params: {min_duration_days: 7, max_duration_days: 365}
  seasonal_signal:
    shape_primitive: cycle
    context_predicate: "dominant_period in {annual, semiannual}"
    detector: etm_harmonics
  common_mode_error:
    shape_primitive: noise
    context_predicate: "spatially_correlated_across_stations"
    detector: common_mode_pca
  tropospheric_delay:
    shape_primitive: noise
    context_predicate: "spatial_atmospheric_pattern"
    detector: gacos_or_pyaps_correction_residual
  unwrapping_error:
    shape_primitive: step
    context_predicate: "step_magnitude in {±2π multiples}"
    detector: phase_jump_2pi_detector
  antenna_offset:
    shape_primitive: step
    context_predicate: "maintenance_log entry at timestamp"
    detector: metadata_driven_step
```

---

## Acceptance Criteria

- [ ] `backend/app/services/semantic_packs/seismo_geodesy.yaml` per schema
- [ ] Loadable via SEG-021 `load_pack('seismo-geodesy')`
- [ ] Every label maps to a shape primitive; validator rejects unknowns
- [ ] Detectors wire to SEG-013 (ETM), SEG-018 (GrAtSiD) — no duplicate fitting logic
- [ ] `sta_lta` helper implemented per Allen 1978 with configurable windows and threshold; uses `obspy` if available, otherwise pure numpy
- [ ] `common_mode_pca` requires multi-station input; gracefully reports `not_applicable` on single station
- [ ] Unwrapping-error detector snaps detected step magnitudes to nearest multiple of `2π` within tolerance `0.1π` (physically motivated)
- [ ] Tests cover: pack loads; each detector callable; synthetic GNSS fixture with coseismic step + postseismic log → labels attached correctly; STA/LTA P-arrival on synthetic seismogram ±2 sample tolerance
- [ ] `obspy` optional dependency (pinned in `backend/requirements-optional.txt` if used)
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper references: Allen 1978 (STA/LTA), Bevis 2014, Bedford & Bevis 2018, Hooper 2012, Ansari 2018. Confirm detector wiring is paper-accurate and ETM/GrAtSiD features are consumed, not recomputed
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "SEG-022: seismo-geodesy semantic pack"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
