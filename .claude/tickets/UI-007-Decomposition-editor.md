# UI-007 — Decomposition editor (Screen D)

**Status:** [ ] Done
**Depends on:** SEG-019 (blob), OP-020..026 (Tier-2 ops)

---

## Goal

Build the central "Decomposition editor" view: a stacked-component visualisation of the active segment's decomposition blob, with per-component edit handles that map directly to Tier-2 ops.

Three features:

**1. Stacked-components view**
One row per named component in `blob.components` (e.g. ETM shows linear, steps, transients, seasonal, residual as separate traces).

**2. Per-component edit handles**
- Linear (trend): slope slider + intercept slider → OP-021 `change_slope` / `linearise`
- Seasonal (cycle): amplitude + phase + period sliders → OP-024 `amplify_amplitude` / `phase_shift` / `change_period`
- Step: Δ slider + `t_s` drag handle on main timeline → OP-022 `scale_magnitude` / `shift_in_time`
- Log/exp transient: amplitude + τ sliders → OP-025 `amplify` / `change_decay_constant`
- Residual: read-only display

**3. Live recomposition preview**
Moving a slider updates the bottom preview in real-time (< 100 ms on 10k-sample segments). Preview is debounced to avoid excessive API calls.

---

## Acceptance Criteria

- [ ] `frontend/src/components/decomposition/DecompositionEditor.vue` main container
- [ ] Subcomponents for each method family: `LinearComponentEditor.vue`, `SeasonalComponentEditor.vue`, `StepComponentEditor.vue`, `TransientComponentEditor.vue`, `ResidualDisplay.vue`
- [ ] Edit handle types match decomposition method (dispatched by `blob.method`)
- [ ] Slider change emits `op-invoked` with appropriate Tier-2 op + params (does not mutate state directly — round-trips through backend)
- [ ] Live preview updates within 100 ms on segments ≤ 10 000 samples (measured via Playwright timing test)
- [ ] "Reset component" button per component reverts to original blob coefficients
- [ ] Undo/redo stack spans editor + palette (shared with UI-015 audit log)
- [ ] ResidualDisplay shows a sparkline + summary stats (mean, std, RMSE from `fit_metadata`)
- [ ] Fixture tests: load ETM blob with 3 components → 3 editor rows; edit slope slider → backend receives `change_slope` call; reset → original coefficients restored
- [ ] `npm test` and `npm run build` pass

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "UI-007: decomposition editor (Screen D)"` ← hook auto-moves this file to `done/` on commit
