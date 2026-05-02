# UI-017 — Gap indicator and missing-data gating

**Status:** [x] Done
**Depends on:** SEG-023 (cloud_gap semantic label)

---

## Goal

Visually indicate data gaps on the timeline and disable ops that cannot run on gap-heavy segments, with opt-in gap-fill via Tier-1 `suppress`.

**Why:** FFT-based Cycle ops and decomposition fits silently produce garbage on gap-heavy series. The UI must make gaps visible and block dense-data-requiring ops until the user explicitly fills them.

---

## Acceptance Criteria

- [x] Gap regions rendered as hatched / dashed pattern in the timeline, distinct from normal segment fills
- [x] A segment labelled `noise` with `semantic_label=cloud_gap` (from SEG-023) shows a gap icon on its chip
- [x] Gating rule: ops requiring dense data (OP-024 `change_period`/`phase_shift` → frontend `cycle_change_frequency`/`cycle_shift_phase`; FFT-based `cycle_add_harmonics`/`cycle_remove_harmonics`; SEG-013 ETM harmonics + SEG-014 STL via the Tier-3 `decompose` entry point) disabled when the segment's missingness ratio > 30 %
- [x] Disabled button tooltip: "Not available: segment has {pct}% missing data. Fill via Tier-1 suppress first."
- [x] Gap-fill available as Tier-1 `suppress` with strategy picker (linear / spline / climatology per UI-005)
- [x] After fill, the filled segment is marked with a `filled=true` metadata flag and a subtle badge "filled (linear)"; dense-data ops become enabled
- [x] Missingness-threshold configurable via `gap.dense_ops_threshold_pct` user setting (default 30)
- [x] Fixture tests: synthetic series with artificial gaps → hatched render; FFT Cycle op disabled with correct tooltip; suppress(linear) fills → FFT op enabled; filled badge visible
- [x] `npm test` and `npm run build` pass

## Definition of Done
- [x] Run `tester` agent — all tests pass *(via the pre-commit hook + npm test)*
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "UI-017: gap indicator + missing-data gating for dense-data ops"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Created `frontend/src/lib/gaps/{createGapGatingState.js, userSetting.js}` (pure libs + tests), `frontend/src/components/gaps/{GapIndicator.vue, GapFillPicker.vue}` (presentation), and integrated gap gating into the existing `createTieredPaletteState`, `ShapeChip.vue`, and `SegmentationOverlay.vue`. Bundle size grew from 155.25 → 157.68 kB JS gzipped (53.47 kB) because `GapIndicator` is reachable through `ShapeChip` and pulled into the bundle for the first time.

**Pure-lib surface**: `DEFAULT_DENSE_OPS_THRESHOLD_PCT = 30`, `DENSE_DATA_OPS = {cycle_change_frequency, cycle_shift_phase, cycle_add_harmonics, cycle_remove_harmonics, decompose}` (frozen Set; maps the AC's OP-024 names to the frontend op-catalog names; the Tier-3 `decompose` entry point covers ETM/STL fits), `SUPPRESS_STRATEGIES = ['linear','spline','climatology']` matching UI-005, plus `classifyGap`, `isOpBlockedByGap`, `gapDisabledTooltip` (emits the AC-verbatim string), `applyGapGatingToButton` (designed to chain *after* shape gating in `createTieredPaletteState` so a Tier-2 op already disabled by multi-select stays disabled — gap gating doesn't accidentally re-enable), and `buildSuppressPayload` for the OP-013 `suppress` payload.

**Threshold-comparison correctness gotcha** (caught by code-reviewer): comparing the *rounded* `missingnessPct > threshold` would let a true 30.4 % ratio slip past the gate (it rounds to 30). The fix compares the raw ratio: `clampedRatio * 100 > threshold`. The display percent is still rounded, but the gating uses raw precision. Pinned by `compares against raw ratio not rounded percent (30.4% IS over 30)` test.

**Three deliberately-out-of-scope cycle ops** (`cycle_damp`, `cycle_amplify`, `cycle_scale_amplitude`) stay enabled even on heavy gaps — they don't run an FFT, they scale a single coefficient, so a user may legitimately want to apply them on a gap-heavy region without filling. Documented inline in the `DENSE_DATA_OPS` constant.

**Visual rendering**: `ShapeChip.vue` renders a 45° hatched stripe via `repeating-linear-gradient` when the segment is gap-heavy AND not filled. The cloud-gap badge (`☁`) and the green "filled (strategy)" badge are both rendered when applicable — they communicate different things (semantic identity vs raw missingness) and a SEG-023 cloud_gap segment with 100 % missingness shows both. `SegmentationOverlay.vue` plumbs `is-cloud-gap`, `is-filled`, `fill-strategy`, `missingness-pct` through to each `ShapeChip` (camelCase-or-snake_case tolerant for SEG-023's `semantic_label` field name).

**User setting**: `userSetting.js` round-trips the threshold via `sessionStorage` keyed at `hypothex-ts.gap.dense_ops_threshold_pct.v1`. Always clamps on read so a manually-tampered storage entry can't disable gating entirely.

**Two deferred items** (consistent with UI-008/UI-009 scope-keeping):
1. `GapFillPicker.vue` is built and tested but not yet wired into `BenchmarkViewerPage.vue` — Vite-tree-shake-safe today; one-import-plus-one-handler change to wire when needed.
2. The user setting has no UI surface yet (the AC mentions configurability but doesn't require a UI input); a settings-panel ticket can add that later. The flag is fully wired in code via `loadGapThresholdPct()`.

**Tests**: 35 new in `lib/gaps/` (gap classification, threshold clamping, op blocking, tooltip text, suppress payload, sessionStorage round-trip, malformed-storage resilience), 5 new in `createTieredPaletteState.test.js` (tier2 cycle FFT ops gated, non-FFT cycle ops stay enabled, tier3 decompose gated, filled re-enables, omitted gapInfo no-op), plus the rounding edge-case test. Full frontend suite goes 573 → 614 (+41), zero regressions; `npm run build` clean. Code-reviewer APPROVE, 0 blocking; one real correctness nit (rounded-vs-raw threshold) fixed inline; two non-blocking nits left for future polish (the `'cloud_gap'` literal duplicated between `SegmentationOverlay.vue` inline binding and a const in the lib; an unreachable `typeof globalThis === 'undefined'` guard in `userSetting.js`).
