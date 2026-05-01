# UI-012 — Plausibility badge

**Status:** [x] Done
**Depends on:** OP-050 (CF coordinator), OP-032 (conservation)

---

## Goal

Per-op-card traffic-light badge (green / amber / red) based on three signals:
1. **In-domain range clipping** — did the edit push values outside the domain's physical range?
2. **Conservation residual** — from OP-032 / UI-010 budget bar
3. **Manifold distance (AE wrapper)** — optional, off by default; distance from training-data manifold via autoencoder wrapper

**Why:** Plausibility is a shorthand signal for "is this CF realistic?" — surfacing it as a badge prevents users from committing obviously implausible edits without thinking.

---

## Acceptance Criteria

- [x] `frontend/src/components/plausibility/PlausibilityBadge.vue` small traffic-light icon (green / amber / red)
- [x] Combined rule: red if any signal red; amber if any amber and no red; green if all green
- [x] Hover shows per-signal breakdown:
  - "Range: within [0, 100]" (green) / "exceeds max by 5" (red)
  - "Residual: 0.01 / tolerance 0.1" (green) / "0.5 / 0.1" (red)
  - "Manifold: 0.3σ" (green) / "4.2σ" (red) / "disabled" (grey)
- [x] Badge placed on every op card and every entry in audit log
- [x] Manifold-distance signal behind a feature flag `plausibility.manifold_ae_enabled` (default false); when disabled, hover shows "Manifold: disabled"
- [x] Accessibility: badge has aria-label reflecting state; not colour-only
- [x] Fixture tests: each signal combination → expected badge colour; tooltip content correct; feature-flag off hides manifold signal
- [x] `npm test` and `npm run build` pass

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "UI-012: plausibility badge (range + residual + manifold)"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Created `frontend/src/lib/plausibility/createPlausibilityBadgeState.js` (pure state) plus three more files in `lib/plausibility/`: `extractSignalsFromEvent.js` (event → signal mapper), `featureFlags.js` (small flag store), and one Vue component `frontend/src/components/plausibility/PlausibilityBadge.vue`. State module exports `STATUS = {GREEN, AMBER, RED, DISABLED}`, `FEATURE_FLAG_MANIFOLD_AE` constant, `MANIFOLD_AMBER_SIGMA = 1` / `MANIFOLD_RED_SIGMA = 3` thresholds, `evaluateRangeSignal`, `evaluateResidualSignal`, `evaluateManifoldSignal`, `combineSignals`, and `createPlausibilityBadgeState`. Combine rule: red if any contributing signal red; amber if any amber and no red; green if every contributing signal green; disabled signals are excluded from combination. Missing data (range/residual null, or manifold null with feature flag on) surfaces as amber rather than green so the badge never overstates confidence — this is the conservative default until OP-032 wires per-law residuals and a future ticket adds range/manifold backend payloads.

The residual signal reuses `classifyResidual` from UI-010's `createConstraintBudgetState.js` (no duplicated hard/soft-law table), so the badge tracks the same green/amber/red rules as the budget bar. The manifold signal is feature-flagged via `getFeatureFlag('plausibility.manifold_ae_enabled')` (default `false`); when disabled the signal is excluded from the combine rule and the hover shows "Manifold: disabled". Number formatting prefers integer display (`100` not `100.00`) to match the AC tooltip examples; trailing-zero stripping handles non-integer values.

`PlausibilityBadge.vue` renders an 18 × 18 px pill with `currentColor` border, status background, and a non-colour glyph (✓ / ! / ✗) so the badge is not colour-only; `role="img"` + `aria-label` carry the full per-signal breakdown for assistive tech, and `:title` gives a sighted-user tooltip. The component is read-only (no events) — placement is the parent's responsibility.

Integrated into two screens: `HistoryPanel.vue` (op cards — added to each `history-item-header` next to the existing status pill via a new `.history-status-group` flex wrapper) and `AuditLogPanel.vue` (audit table — added as a new leftmost "Plausibility" column). The audit log's existing string-derived "Plausibility" column / filter / detail-pane field was renamed to "Confidence" since it actually shows confidence-band derived from `chip.confidence` — keeping both: the underlying field name `plausibilityBadge` is unchanged so UI-015's CSV/JSON export schema remains stable. `createHistoryEntries.js` was extended to forward `constraintResidual`, `plausibilityRange`, and `plausibilityManifold` from raw events into history entries so the badge can read them.

Fixture coverage: 31 tests in `createPlausibilityBadgeState.test.js` (per-signal evaluators × 5 / 5 / 5, combineSignals × 5, badge state combinations × 6, accessibility / tooltip × 3, defaults × 1, plus 1 unit-test for `combineSignals` ignoring null entries), 6 tests in `extractSignalsFromEvent.test.js`. `npm test` 472 / 472 pass; `npm run build` clean (144.61 kB JS / 24.35 kB CSS, 49.52 kB / 5.15 kB gzipped). Code-reviewer approved with no blocking issues; addressed the unused-export nit by importing `FEATURE_FLAG_MANIFOLD_AE` from the state module in both Vue components instead of duplicating the literal string. Two remaining nits (non-reactive `getFeatureFlag` read at script-setup time, multi-line `title` attribute rendering) are non-blocking and documented for future flag-toggle work.
