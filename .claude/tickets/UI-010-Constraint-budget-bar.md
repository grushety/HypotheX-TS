# UI-010 — Constraint-budget bar

**Status:** [ ] Done
**Depends on:** OP-032 (enforce_conservation), OP-051 (compensation projection)

---

## Goal

Visual budget bar showing the conservation-law residual before and after the current op. Clicking the bar expands a panel showing residual broken down by constraint component (e.g. water balance: P, ET, Q, ΔS contributions).

**Why:** This is the UI surface for HypotheX-TS's flagship conservation claim. Without a visible budget bar, the "first-class user-exposed conservation" contribution is invisible to the user and to reviewers.

---

## Acceptance Criteria

- [ ] `frontend/src/components/constraints/ConstraintBudgetBar.vue` horizontal bar component
- [ ] Colour: green = within tolerance, amber = over tolerance but soft law, red = hard law violated
- [ ] Pre/post markers shown when compensation mode ≠ `naive`; arrow indicating direction of change
- [ ] Hover shows numeric residual: `"Δ = 0.023 mm/day (of 0.10 tolerance)"`
- [ ] Click expands `ConstraintResidualBreakdown.vue` panel showing per-component contribution (water balance: {P, ET, Q, ΔS}; moment balance: {Mxx, Myy, Mzz})
- [ ] Updates reactively as the user changes compensation mode (UI-011)
- [ ] Reads from the `constraint_residual` field of the `CFResult` returned by OP-050
- [ ] Accessibility: numeric residual also announced via `aria-live="polite"` on change; not colour-only
- [ ] Fixture tests: green for satisfied constraint; amber for soft-violated; red for hard-violated; breakdown shows all components; compensation-mode change updates pre/post markers
- [ ] `npm test` and `npm run build` pass

## Definition of Done
- [ ] Run `test-writer` agent — colour thresholds, hover tooltip, click breakdown, reactive update
- [ ] Run `code-reviewer` agent — no blocking issues; no colour-only communication
- [ ] `git commit -m "UI-010: constraint-budget bar with per-component breakdown"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
