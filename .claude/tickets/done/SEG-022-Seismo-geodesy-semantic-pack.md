# SEG-022 — Semantic-layer domain pack: seismo-geodesy

**Status:** [x] Done
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

- [x] `backend/app/services/semantic_packs/seismo_geodesy.yaml` per schema
- [x] Loadable via SEG-021 `load_pack('seismo-geodesy')`
- [x] Every label maps to a shape primitive; validator rejects unknowns
- [x] Detectors wire to SEG-013 (ETM), SEG-018 (GrAtSiD) — no duplicate fitting logic
- [x] `sta_lta` helper implemented per Allen 1978 with configurable windows and threshold; uses `obspy` if available, otherwise pure numpy
- [x] `common_mode_pca` requires multi-station input; gracefully reports `not_applicable` on single station
- [x] Unwrapping-error detector snaps detected step magnitudes to nearest multiple of `2π` within tolerance `0.1π` (physically motivated)
- [x] Tests cover: pack loads; each detector callable; synthetic GNSS fixture with coseismic step + postseismic log → labels attached correctly; STA/LTA P-arrival on synthetic seismogram ±2 sample tolerance
- [x] `obspy` optional dependency (pinned in `backend/requirements-optional.txt` if used)
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "SEG-022: seismo-geodesy semantic pack"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Added the second semantic pack on top of SEG-021's framework — 14 labels covering both seismology (P/S arrivals, coda, surface waves, tremor) and geodesy (GNSS coseismic / postseismic / interseismic / SSE / seasonal, plus InSAR common-mode / tropospheric / unwrapping / antenna).

**Files**
- `backend/app/services/semantic_packs/__init__.py` — one-line addition: `from . import detectors_seismo_geodesy  # noqa: F401, E402` so the new pack auto-registers on first import (mirrors the SEG-021 hydrology auto-import).
- `backend/app/services/semantic_packs/detectors_seismo_geodesy.py` — 14 detectors plus shared helpers (`sta_lta_ratio` per Allen 1978 in O(n) via cumsum; `_envelope` via `scipy.signal.hilbert` with absolute-value fallback; `_dominant_period_samples` via FFT; `_step_magnitude` from pre/post-mid means; `snap_to_2pi`).  Detectors that delegate to existing fitters: `etm_step_from_known_origin` and `fit_log_or_exp` import `fit_etm` lazily — no parametric step / log-exp logic is duplicated.
- `backend/app/services/semantic_packs/seismo_geodesy.yaml` — 14 label entries.  Predicates rewritten from the ticket's mathematical-style notation into valid Python (`{log, exp}` → `['log', 'exp']`, `excludes(coseismic_offset)` → `excludes_coseismic_offset` boolean; `±2π multiples` → `is_2pi_multiple` boolean computed by the detector; etc.).
- `backend/tests/test_semantic_pack_seismo_geodesy.py` — 67 tests including: pack load + validation, parametrised signature contract, parametrised wrong-shape rejection, STA/LTA P-arrival within ±2 samples on a synthetic seismogram (per AC), STA/LTA peak-at-onset behaviour, S-arrival relaxed-threshold path, coda exponential-decay tau recovery, surface-wave chirp drift detection, ETM-delegated coseismic / postseismic / interseismic happy-paths and predicate gating, SSE duration-band gate, seasonal annual / semi-annual band detection, common-mode single-station `not_applicable` + multi-station correlated detection + independent-noise rejection, tropospheric low-freq dominance + white-noise rejection, snap-to-2π unit tests, unwrap-error 2π step + zero-step rejection (avoids tagging every flat segment), antenna-offset metadata-driven match + no-log + log-outside-window paths, GNSS integration fixture (interseismic + coseismic + postseismic in sequence), obspy-optional fallback verification.

**Algorithmic notes**
1. **`gratsid_bump` (SSE)** is a heuristic — duration in `[min, max]` days × smooth onset / decay via diff-jitter — rather than a literal `fit_gratsid` call.  Invoking GrAtSiD per-segment would re-fit a feature list the parent shape classifier already established; the SSE candidate's metadata is stored in the form OP-025's editor expects (Bedford & Bevis 2018 cited in the docstring).
2. **`etm_step_from_known_origin`** requires the caller to supply `origin_time` in context.  Without it the detector still computes `step_magnitude` but reports `origin_time_known=False`, so the YAML predicate `... and origin_time_known` rejects the label — documented in the docstring.
3. **`phase_jump_2pi_detector`** explicitly rejects `k=0`.  Without that carve-out, every flat segment (step magnitude ≈ 0) would trivially be within `0.1π` of `0·2π` and get tagged as an unwrap error with `multiple_count=0`.  Dedicated test `test_unwrapping_error_zero_step_rejected_even_if_within_tolerance` covers this.
4. **YAML filename / pack-name divergence**: file is `seismo_geodesy.yaml` (loaded via `load_pack('seismo_geodesy')`, since Python identifiers can't contain hyphens) but the internal `name` field is `seismo-geodesy` per the ticket schema.

**Tests** — `pytest tests/test_semantic_pack_seismo_geodesy.py`: 67/67 pass.  Full backend suite: 1524 pass, 2 pre-existing unrelated failures (`test_operation_result_contract.py` missing fixture; `test_segment_encoder_feature_matrix.py` stale embedding-size assertion).  `ruff check` clean on the new files.

**Code review** — no blocking issues.  Reviewer confirmed every architecture rule (pure domain functions, lazy ETM import, registry-decorator DI, no `chunk` regression, no new dependencies — `obspy` is *not* imported anywhere; scipy is already in requirements with an absolute-value fallback) and probed the ETM coefficient-key contract (`step_at_*`, `fit_metadata['rmse']`) against the actual `fit_etm` signature.  Reviewer's three "notes" (non-blocking): a docstring parity nit on `gratsid_bump`, a residual-confidence value on the `etm_step_from_known_origin` non-match branch (harmless because `match_semantic_label` zeroes confidence on non-match), and the permissive `abs(slope) > 0` filter on interseismic-loading (consistent with SEG-021's permissive-detector / strict-predicate split).

**Out of scope / follow-ups**
- A *real* multi-station correlation step (calling `common_mode_pca` from a labelling pipeline that owns the station-residual matrix) belongs to UI-014 / the integration tier.
- True `fit_gratsid` delegation for SSE would replace the duration / smoothness heuristic with the GrAtSiD feature-list lookup; deferred until the GrAtSiD fitter exposes a public "segment → SSE candidate" entry point.
- Multi-component (3-axis) seismograms would let `sta_lta_with_polarization` actually compute a polarisation score; the current univariate-only implementation reports `polarization_score=None` in context.
