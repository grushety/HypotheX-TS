# UI-010 — Constraint-budget bar

**Status:** [x] Done
**Depends on:** OP-032 (enforce_conservation), OP-051 (compensation projection)

---

## Goal

Visual budget bar showing the conservation-law residual before and after the current op. Clicking the bar expands a panel showing residual broken down by constraint component (e.g. water balance: P, ET, Q, ΔS contributions).

**Why:** This is the UI surface for HypotheX-TS's flagship conservation claim. Without a visible budget bar, the "first-class user-exposed conservation" contribution is invisible to the user and to reviewers.

---

## Acceptance Criteria

- [x] `frontend/src/components/constraints/ConstraintBudgetBar.vue` horizontal bar component
- [x] Colour: green = within tolerance, amber = over tolerance but soft law, red = hard law violated
- [x] Pre/post markers shown when compensation mode ≠ `naive`; arrow indicating direction of change
- [x] Hover shows numeric residual: `"Δ = 0.023 mm/day (of 0.10 tolerance)"`
- [x] Click expands `ConstraintResidualBreakdown.vue` panel showing per-component contribution (water balance: {P, ET, Q, ΔS}; moment balance: {Mxx, Myy, Mzz})
- [x] Updates reactively as the user changes compensation mode (UI-011)
- [x] Reads from the `constraint_residual` field of the `CFResult` returned by OP-050
- [x] Accessibility: numeric residual also announced via `aria-live="polite"` on change; not colour-only
- [x] Fixture tests: green for satisfied constraint; amber for soft-violated; red for hard-violated; breakdown shows all components; compensation-mode change updates pre/post markers
- [x] `npm test` and `npm run build` pass

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "UI-010: constraint-budget bar with per-component breakdown"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Created the UI surface for HypotheX-TS's flagship conservation-enforcement claim — a per-law residual bar that mirrors the OP-032 / OP-051 backend semantics into a status-coloured visual with click-to-expand per-component breakdown.

**Files**
- `frontend/src/lib/constraints/createConstraintBudgetState.js` — pure state module:
  - `classifyResidual(residual, tolerance, law) → 'green' | 'amber' | 'red'`
  - `formatResidual(value, units)` — fixed/scientific chooser; handles null / NaN / 0 / negative; appends units when supplied
  - `classifyDirection(initial, final) → 'improving' | 'worsening' | 'unchanged'`
  - `createConstraintBudgetState({...}) → 18-field view model` (status, fillFraction, initialFillFraction, showPrePost, direction, formattedResidual / formattedInitial / formattedTolerance, ariaText, hoverText, isHardLaw, isSoftLaw, plus the originals)
  - `buildBreakdown(law, components, units) → {items, total, supported, formattedTotal}` — per-law per-component decoder for water/moment/phase/NNR; sign tables mirror each law's residual equation
  - Constants: `HARD_LAWS`, `SOFT_LAWS`, `DEFAULT_TOLERANCE` (mirrors OP-032 backend), `STATUS`, `FILL_CAP=1.5`, `SUPPORTED_BREAKDOWN_LAWS`
- `frontend/src/lib/constraints/createConstraintBudgetState.test.js` — 53 tests covering: hard/soft partition, all status branches (green / amber / red / unknown-law-as-amber / NaN-as-amber / boundary-inclusive), formatter edge cases (large / small / mid / zero / null / NaN / negative / units), direction classifier, view-model field surface, compensation-mode-driven `showPrePost`, fillFraction caps + zero, hover-text matches the AC string, ariaText changes between naive and projected modes, default-tolerance fallback, missing-residual defaults, isHardLaw/isSoftLaw flags, breakdown ordering + signs + totals for all four supported laws, unknown-law `supported=false`, non-finite-component skip, formatted strings ready for the UI.
- `frontend/src/components/constraints/ConstraintBudgetBar.vue` — Vue 3 SFC. Uses a `<button>` toggle for keyboard accessibility (Enter/Space, focus-visible outline). Pure CSS bar (no SVG): absolute-positioned fill via `currentColor` so the status class colour propagates, plus tolerance-marker, initial-marker, final-marker. `aria-live="polite"` region with the full announcement (sr-only `clip` pattern). `:title` carries the AC-spec hover text. The local `internalExpanded` ref is mirrored from the `expanded` prop *and* watched so a parent using the bar as a controlled component sees updates after mount.
- `frontend/src/components/constraints/ConstraintResidualBreakdown.vue` — Vue 3 SFC. Renders a `<table>` with Component / Value / Sign / Contribution columns plus a `<tfoot>` showing the residual reconstructed from the components. Falls back to a plain-text "no breakdown available" line when `supported=false`.

**Implementation notes**

1. **Status logic**: `|r| ≤ tolerance` → green; over tolerance + hard law → red; over tolerance + soft (or unknown) law → amber.  Boundary is inclusive (exactly at tolerance is still green).
2. **`FILL_CAP=1.5`** caps the bar fill at `1.5×` tolerance so a runaway 10⁶× residual does not break the layout.  The CSS `tolerance-marker` sits at `66.6667%` because `1/FILL_CAP = 1/1.5`; both the JS template style (`fillFraction * (100/1.5)`) and the CSS depend on `FILL_CAP` — documented inline so a future change updates both.
3. **Pre/post markers** only appear when `compensationMode != 'naive'` *and* both residuals are present.  Naive mode is the "report only" path — there's no projected residual to compare against.
4. **`aria-live="polite"`** announcement is intentionally richer than the visible readout: it includes the law name, status word, direction, and both residuals (when in a projected mode).  Visually hidden via the standard sr-only `clip: rect(0,0,0,0)` pattern; the visible `.constraint-budget-bar__readout` shows the AC's hover text for sighted users.
5. **Controlled-prop watcher**: the `expanded` prop is mirrored into a local `ref` *and* `watch`-ed.  Without the watch, a parent passing `expanded` reactively would see the first value applied at mount but later updates would silently no-op (code-reviewer caught the trap).
6. **Per-component sign tables** in `buildBreakdown` mirror each law's residual equation literally — water balance is `+P − ET − Q − ΔS`, phase closure is `+φ12 + φ23 − φ13`, etc. — so the sum of signed contributions reconstructs the residual the user sees on the bar.

**Tests** — `npm test`: 358/358 pass (305 pre-existing + 53 new).  `npm run build`: clean (132.96 kB JS / 21.47 kB CSS gzipped 45.56 + 4.48).  `npm run lint`: clean on the new files (pre-existing trailing-whitespace warnings in `OperationPalette.vue` predate this branch and are unrelated).

**Code review** — APPROVE, no blocking issues.  Reviewer scrutinised four design choices (sr-only aria-live duplicate, `title`-attribute hover tooltip, sharp 0.001 fixed-vs-scientific transition, `66.6667%` CSS magic number) and accepted all four for MVP.  Two minor non-blocking observations addressed in the same commit: added `watch(() => props.expanded)` to fix a controlled-prop trap; removed an unused `constraint-budget-bar--expanded` class binding that had no matching CSS rule.

**Out of scope / follow-ups**
- Wiring the bar into `BenchmarkViewerPage.vue` next to the operation palette so it updates on every CF synthesis result — belongs to the screen-integration ticket once OP-050 is wired into the page.
- A custom keyboard-accessible tooltip (instead of the native `title` attribute) for richer hover content.
- A CSS custom property `--fill-cap` derived from JS so the `66.6667%` magic number is centralised; defer until the cap value is questioned in practice.
- Bar grouping when multiple constraints are active simultaneously (the current component renders one law at a time; a parent `ConstraintBudgetPanel` could stack them).
