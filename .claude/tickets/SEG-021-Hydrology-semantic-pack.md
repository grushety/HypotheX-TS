# SEG-021 — Semantic-layer domain pack: hydrology

**Status:** [ ] Done
**Depends on:** SEG-008 (shape classifier), SEG-016 (Eckhardt fitter); [[HypotheX-TS - Label Vocabulary Research]]

---

## Goal

Seed a hydrology & climate domain pack that attaches semantic labels to shape-primitive segments. Coverage: `baseflow, stormflow, peak_flow, rising_limb, recession_limb, snowmelt_freshet, drought, ENSO_phase, PDO_phase`.

Each semantic label is defined compositionally as `(shape_primitive, detector, context_predicate)` per [[HypotheX-TS - Formal Definitions]] §2.3.

**Why:** The shape layer alone gives structural types (trend, plateau, cycle...); hydrologists reason in baseflow / storm / drought units. The semantic layer maps shape segments into domain vocabulary so the operation palette (UI-005) shows domain-meaningful names rather than abstract `plateau-012`.

**How it fits:** Pack is loaded by UI-014 (domain pack selector). Detectors run after SEG-008 shape classification; shape labels remain unchanged (shape = ground truth), semantic labels are layered on top. User-defined labels shadow pack labels per [[HypotheX-TS - Implementation Plan]] §8.4.

---

## Paper references (for `algorithm-auditor`)

- Eckhardt (2005) "How to construct recursive digital filters for baseflow separation" — *Hydrological Processes* 19:507 (baseflow, BFI).
- Tallaksen (1995) "A review of baseflow recession analysis" — *J. Hydrology* 165:349–370 (recession).
- Wolter & Timlin (2011) "El Niño/Southern Oscillation behaviour since 1871 as diagnosed in an extended multivariate ENSO index" — *Int. J. Climatology* 31(7):1074 (MEI / ENSO).
- Mantua, Hare (2002) "The Pacific Decadal Oscillation" — *J. Oceanography* 58:35–44 (PDO).

---

## Pack schema (YAML)

```yaml
name: hydrology
version: 1.0
semantic_labels:
  baseflow:
    shape_primitive: plateau
    context_predicate: "Q < BFImax * Q_median"
    detector: eckhardt_baseflow
    detector_params: {BFImax: 0.8, a: 0.98}
  stormflow:
    shape_primitive: transient
    context_predicate: "rising_limb_detected and peak_Q > 3 * Q_median"
    detector: peak_detection_plus_ascending_limb_fit
    detector_params: {peak_ratio_threshold: 3.0}
  peak_flow:
    shape_primitive: spike
    context_predicate: "max(Q) > 5 * Q_median and duration < 3 * dt"
    detector: hampel_peak
  rising_limb:
    shape_primitive: trend
    context_predicate: "slope > 0 and preceded_by(baseflow)"
    detector: slope_sign_plus_context
  recession_limb:
    shape_primitive: trend
    context_predicate: "slope < 0 and |slope| < recession_slope_max and follows(peak_flow)"
    detector: slope_sign_plus_context
    detector_params: {recession_slope_max: 0.1}
  snowmelt_freshet:
    shape_primitive: transient
    context_predicate: "spring_timing and sustained_rise_over_weeks"
    detector: seasonal_context_plus_transient_fit
  drought:
    shape_primitive: plateau
    context_predicate: "Q < 0.1 * Q_median for duration > 30 days"
    detector: low_flow_threshold_plus_duration
  ENSO_phase:
    shape_primitive: cycle
    context_predicate: "dominant_period in [2, 7] years"
    detector: mei_index_plus_period_check
  PDO_phase:
    shape_primitive: cycle
    context_predicate: "dominant_period in [15, 30] years"
    detector: pdo_index_plus_period_check
```

---

## Acceptance Criteria

- [ ] `backend/app/services/semantic_packs/hydrology.yaml` following schema above
- [ ] `backend/app/services/semantic_packs/__init__.py` with `load_pack(name: str) -> SemanticPack`
- [ ] `SemanticPack` data class with `name`, `version`, `semantic_labels: dict[str, SemanticLabel]`
- [ ] Each `SemanticLabel` maps to exactly one shape primitive (validated at load time; raises on unknown shape)
- [ ] Each detector callable with signature `(X_seg, shape_label, context) -> (matched: bool, confidence: float)`
- [ ] Detector registry `DETECTOR_REGISTRY: dict[str, Callable]`; detectors registered via decorator
- [ ] Pack loads without errors; every named detector resolves in the registry
- [ ] Detectors delegate to existing fitters where possible (e.g. `baseflow` calls SEG-016 `eckhardt_baseflow`; no duplicate baseflow logic)
- [ ] Context evaluator parses simple context predicates from YAML (e.g. `"Q < BFImax * Q_median"`) — MVP uses Python `eval` on a restricted namespace
- [ ] User-defined labels shadow pack labels per-project (documented in pack loader)
- [ ] Tests cover: pack YAML loads; each semantic label maps to valid shape; each detector returns `(bool, float)`; hydrograph fixture with known baseflow/stormflow segments → expected semantic labels attached
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — all tests pass
- [ ] Run `algorithm-auditor` agent with paper references: Eckhardt 2005, Tallaksen 1995, Wolter & Timlin 2011, Mantua & Hare 2002. Confirm each detector threshold is cited to its source paper (or labeled `empirical` with test-fixture justification); no thresholds invented without citation
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "SEG-021: hydrology semantic pack (baseflow, storm, ENSO, PDO)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
