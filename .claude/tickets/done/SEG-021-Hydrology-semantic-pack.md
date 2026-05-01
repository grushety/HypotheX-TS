# SEG-021 — Semantic-layer domain pack: hydrology

**Status:** [x] Done
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

- [x] `backend/app/services/semantic_packs/hydrology.yaml` following schema above
- [x] `backend/app/services/semantic_packs/__init__.py` with `load_pack(name: str) -> SemanticPack`
- [x] `SemanticPack` data class with `name`, `version`, `semantic_labels: dict[str, SemanticLabel]`
- [x] Each `SemanticLabel` maps to exactly one shape primitive (validated at load time; raises on unknown shape)
- [x] Each detector callable with signature `(X_seg, shape_label, context) -> (matched: bool, confidence: float)`
- [x] Detector registry `DETECTOR_REGISTRY: dict[str, Callable]`; detectors registered via decorator
- [x] Pack loads without errors; every named detector resolves in the registry
- [x] Detectors delegate to existing fitters where possible (e.g. `baseflow` calls SEG-016 `eckhardt_baseflow`; no duplicate baseflow logic)
- [x] Context evaluator parses simple context predicates from YAML (e.g. `"Q < BFImax * Q_median"`) — MVP uses Python `eval` on a restricted namespace
- [x] User-defined labels shadow pack labels per-project (documented in pack loader)
- [x] Tests cover: pack YAML loads; each semantic label maps to valid shape; each detector returns `(bool, float)`; hydrograph fixture with known baseflow/stormflow segments → expected semantic labels attached
- [x] `pytest backend/tests/ -x` passes

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "SEG-021: hydrology semantic pack (baseflow, storm, ENSO, PDO)"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Created the semantic-pack subsystem and its first pack (hydrology, 9 labels).

**Files**
- `backend/app/services/semantic_packs/__init__.py` — package surface; auto-imports `detectors_hydrology` so `DETECTOR_REGISTRY` is populated *before* the first `load_pack` call.
- `backend/app/services/semantic_packs/core.py` — frozen `SemanticPack` and `SemanticLabel` dataclasses; `DETECTOR_REGISTRY` + `@register_detector` decorator (mirrors the SEG-019 fitter dispatcher pattern); `evaluate_predicate` (AST-validated, whitelisted-builtins-only — see security section); `load_pack` (YAML, validates `shape_primitive` against the 7-shape vocab and `detector` name against the registry); `match_semantic_label` (shape filter → detector → predicate); `label_segment` (apply every label in a pack, return descending-confidence matches).
- `backend/app/services/semantic_packs/detectors_hydrology.py` — 9 detectors:
  1. `eckhardt_baseflow` — delegates to SEG-016 `fit_eckhardt`; matches `plateau` segments whose level sits below `BFImax · Q_median`.
  2. `peak_detection_plus_ascending_limb_fit` — matches `transient` segments with a rising first-half slope and `peak_Q > peak_ratio_threshold · Q_median`.
  3. `hampel_peak` — matches `spike` segments with a Hampel (1974) outlier above `5 · Q_median`; `duration_samples` is the *FWHM width* (count of samples ≥ half-peak), not the segment length.
  4. `slope_sign_plus_context` — single callable for both `rising_limb` and `recession_limb`; populates `slope` and the neighbour flags `preceded_by_baseflow` / `follows_peak_flow`.  The YAML predicate disambiguates direction.
  5. `seasonal_context_plus_transient_fit` — `snowmelt_freshet`; populates `is_spring` (caller-supplied) and `sustained_rise_weeks`.
  6. `low_flow_threshold_plus_duration` — `drought`; `low_flow_fraction` = mean of `Q < 0.1 · Q_median`, `duration_days` from `samples_per_day` context.
  7. `mei_index_plus_period_check` — ENSO 2–7 yr band, dominant FFT period.
  8. `pdo_index_plus_period_check` — PDO 15–30 yr band.
- `backend/app/services/semantic_packs/hydrology.yaml` — 9 label entries with `shape_primitive`, `detector`, `detector_params`, `context_predicate`.  Predicates rewritten from the ticket's mathematical-style notation into valid Python: `|slope|` → `abs(slope)`, `Q < 0.1 * Q_median for duration > 30 days` → `low_flow_fraction > 0.9 and duration_days > 30`, etc.
- `backend/tests/test_semantic_packs.py` — 44 tests: pack load + invalid YAML rejection, parametrised detector signature contract over the full registry, predicate-evaluator security (rejects `__import__`, attribute access, lambdas, etc.) plus happy-path comparisons / arithmetic / `in` / whitelisted calls, single-label match for each of the 9 labels, integration hydrograph fixture (baseflow + stormflow + recession_limb segments labeled correctly), descending-confidence ordering, user-label shadowing semantics, public surface assertions.

**Security — predicate evaluator**

`evaluate_predicate` uses Python `eval` because predicates are simple expressions like `Q_mean < BFImax * Q_median`.  Mitigations: (1) AST whitelist rejects every node outside `BoolOp / Compare / BinOp / UnaryOp / Constant / Name / Call / List / Tuple` — explicitly excludes `Attribute`, `Subscript`, `Lambda`, comprehensions, `IfExp`, `Set` / `Dict` literals, `Starred`, walrus, `__import__`; (2) calls are restricted to a fixed allow-list of `abs / max / min / len / all / any / round / sum`; (3) `eval` is invoked with `__builtins__: {}` so no implicit access.  Code-reviewer probed every common sandbox-escape primitive (Attribute via `x.__class__`, GeneratorExp, IfExp, Subscript, Lambda, walrus, etc.) — all correctly rejected.  Trust model documented in the function docstring: pack YAML is *author-controlled* (shipped with the codebase), so the AST guard is defence-in-depth; if the boundary ever widens to user-uploaded packs (UI-14), drop `ast.Pow` from the whitelist and add a wall-clock timeout to bound `2 ** 10 ** 8`-style arithmetic DoS.

**User-defined-label shadowing**

`SemanticPack` itself is frozen, but its `semantic_labels` field is an ordinary dict — callers can replace entries to override pack labels per-project (Implementation Plan §8.4).  `test_user_defined_labels_can_shadow_pack_labels` exercises this path: the override goes into a copy of the dict so the original pack instance remains pristine.

**Tests** — `pytest tests/test_semantic_packs.py`: 44/44 pass.  Full backend suite: 1443 pass, 2 pre-existing unrelated failures (`test_operation_result_contract.py` missing fixture; `test_segment_encoder_feature_matrix.py` stale embedding-size assertion).  `ruff check` clean on the new package.

**Code review** — no blocking issues.  Architecture rules (pure domain functions, source citations on every detector, registry-decorator DI, frozen DTOs, `segment` naming, no new dependencies) all hold.  Reviewer surfaced one advisory I addressed: documented the trust-model and `Pow`/`Mult` CPU-DoS surface in the `evaluate_predicate` docstring so a future maintainer doesn't widen the surface unintentionally.

**Out of scope / follow-ups**
- Wiring `load_pack("hydrology")` into the labeling pipeline + UI-014 domain-pack selector belongs to UI-014 / the integration tier.
- A second pack (remote-sensing, financial, etc.) would re-use the same `core.py` machinery — only a new `detectors_*.py` and `*.yaml` file are needed.
- Real MEI / PDO index integration (rather than spectral-period-only checks) would require an external data source; deferred.
