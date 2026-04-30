# UI-016 — Parameter sliders (amplify/dampen disambiguation)

**Status:** [x] Done
**Depends on:** OP-010 (scale), OP-023 (Spike amplify), OP-024 (Cycle amplify/dampen), OP-025 (Transient amplify/dampen), OP-026 (Noise amplify)

---

## Goal

For ops with ambiguous verb pairs (e.g. `amplify` vs `dampen` — both are `scale` with α > 1 or α < 1), replace the pair of buttons with a single **log-scaled slider** that disambiguates via sign.

**Why:** Showing "amplify" and "dampen" as two buttons hides that they are the same op with different parameter ranges and causes users to jump between buttons when tuning. A single slider exposes the continuity.

---

## Acceptance Criteria

- [x] `frontend/src/components/palette/AmplitudeSlider.vue` single slider component, log-scaled over `[0.01, 100]` with default 1.0 (identity)
- [x] Visual zones: left of 1.0 = blue (dampen) with label "dampen"; right of 1.0 = red (amplify) with label "amplify"
- [x] Numeric readout alongside slider (both linear α and multiplicative label like "×2.0" or "×0.5")
- [x] Snap-to-common-values on hover near 0.5, 1.0, 2.0, 10.0 (within ±5 % snap threshold)
- [x] Replaces the amplify / dampen button pair in:
  - OP-024 Cycle (amplify_amplitude / dampen_amplitude)
  - OP-025 Transient (amplify / dampen)
  - OP-026 Noise (amplify)
  - OP-023 Spike (amplify only; single direction)
- [x] Commits on slider release (not on every drag event) to avoid API storm
- [x] Keyboard: arrow keys adjust by 1 % log-step; Home/End jump to extrema; `1` key snaps to identity
- [x] Fixture tests: slider value 0.5 → dampen (α=0.5); value 2.0 → amplify (α=2.0); value 1.0 → identity (no API call); snap behaviour at common values
- [x] `npm test` and `npm run build` pass

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "UI-016: parameter sliders for amplify/dampen disambiguation"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Replaced the amplify/dampen button pair with a single log-scaled slider that disambiguates direction by sign of `(α − 1)`.

**New files**
- `frontend/src/lib/operations/amplitudeSlider.js` — pure log-scale helpers: `positionToAlpha`, `alphaToPosition`, `snapToCommon`, `classify`, `stepAlpha`, `formatMultiplier`, `isIdentity`. Range `[0.01, 100]`; identity at the slider midpoint (t=0.5). The classifier uses a `1e-9` tolerance so floating-point noise around 1.0 still classifies as `identity` (no API call).
- `frontend/src/lib/operations/amplitudeSlider.test.js` — 26 unit tests covering log-scale round-trip, classification, snap thresholds, keyboard step, and clamping.
- `frontend/src/lib/operations/sliderOps.js` — registry mapping `cycle_amplify`, `cycle_damp`, `transient_scale`, `spike_scale`, `noise_rescale` to a slider config (`groupId`, `mode`, `commitOpName`, `paramKey`). `groupTier2Controls(buttons)` collapses two ops sharing a `groupId` into one slider entry while preserving first-occurrence order; unknown ops fall through as plain buttons.
- `frontend/src/lib/operations/sliderOps.test.js` — 13 tests covering registry shape, grouping, ordering, single-member sliders, multi-member enable/loading aggregation.
- `frontend/src/components/palette/AmplitudeSlider.vue` — Vue component. Native `<input type="range">` quantised to a 1000-step integer track. Emits `commit` on `change` (drag release) and after each keyboard step. Keyboard: ArrowLeft/Down = −1 % log-step, ArrowRight/Up = +1 % log-step, Home/End = extrema, Enter = commit, `1` = reset to identity (no commit). `mode="amplify-only"` for spike clamps the lower bound to 1.0. Visual zones (blue/red), numeric readout (×N + α=…), reset button.

**Modified**
- `frontend/src/components/palette/OperationPalette.vue` — imports `AmplitudeSlider` and `groupTier2Controls`; renders the Tier-2 row from a `tier2Controls` computed that returns either `{kind: 'button'}` or `{kind: 'slider'}` entries. Slider commits emit `op-invoked` with `{tier, op_name: commitOpName, params: {alpha}}`. The catalog and `SHAPE_GATING_TABLE` are untouched, so existing gating tests stay green.

**Tests** — frontend `npm test`: 344/344 pass (39 new). `npm run build`: clean (139.5 kB JS / 23.55 kB CSS).

**Code review** — no blocking issues. Architecture rules (pure logic in `lib/`, no fetch in components, no `chunk` regression, no new dependencies) all hold; emitted payload shape lines up with backend `amplify_amplitude` / `transient_scale` / `spike_scale` / `noise_rescale` signatures and is forward-compatible with the (still pending) tier-2 wiring in `BenchmarkViewerPage.handleOpInvoked`.

**Out of scope / follow-ups**
- Wiring tier-2 ops (including the slider's commit payload) to the backend lives outside this ticket; today's `handleOpInvoked` still surfaces "not yet implemented" for tier-2.
- Live preview / PROJECTED constraint feedback while dragging is a separate UI ticket.
