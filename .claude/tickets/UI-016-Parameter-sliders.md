# UI-016 — Parameter sliders (amplify/dampen disambiguation)

**Status:** [ ] Done
**Depends on:** OP-010 (scale), OP-023 (Spike amplify), OP-024 (Cycle amplify/dampen), OP-025 (Transient amplify/dampen), OP-026 (Noise amplify)

---

## Goal

For ops with ambiguous verb pairs (e.g. `amplify` vs `dampen` — both are `scale` with α > 1 or α < 1), replace the pair of buttons with a single **log-scaled slider** that disambiguates via sign.

**Why:** Showing "amplify" and "dampen" as two buttons hides that they are the same op with different parameter ranges and causes users to jump between buttons when tuning. A single slider exposes the continuity.

---

## Acceptance Criteria

- [ ] `frontend/src/components/palette/AmplitudeSlider.vue` single slider component, log-scaled over `[0.01, 100]` with default 1.0 (identity)
- [ ] Visual zones: left of 1.0 = blue (dampen) with label "dampen"; right of 1.0 = red (amplify) with label "amplify"
- [ ] Numeric readout alongside slider (both linear α and multiplicative label like "×2.0" or "×0.5")
- [ ] Snap-to-common-values on hover near 0.5, 1.0, 2.0, 10.0 (within ±5 % snap threshold)
- [ ] Replaces the amplify / dampen button pair in:
  - OP-024 Cycle (amplify_amplitude / dampen_amplitude)
  - OP-025 Transient (amplify / dampen)
  - OP-026 Noise (amplify)
  - OP-023 Spike (amplify only; single direction)
- [ ] Commits on slider release (not on every drag event) to avoid API storm
- [ ] Keyboard: arrow keys adjust by 1 % log-step; Home/End jump to extrema; `1` key snaps to identity
- [ ] Fixture tests: slider value 0.5 → dampen (α=0.5); value 2.0 → amplify (α=2.0); value 1.0 → identity (no API call); snap behaviour at common values
- [ ] `npm test` and `npm run build` pass

## Definition of Done
- [ ] Run `test-writer` agent — log scale, snap, visual zones, debounced commit, keyboard
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "UI-016: parameter sliders for amplify/dampen disambiguation"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
