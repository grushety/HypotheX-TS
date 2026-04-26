# UI-012 — Plausibility badge

**Status:** [ ] Done
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

- [ ] `frontend/src/components/plausibility/PlausibilityBadge.vue` small traffic-light icon (green / amber / red)
- [ ] Combined rule: red if any signal red; amber if any amber and no red; green if all green
- [ ] Hover shows per-signal breakdown:
  - "Range: within [0, 100]" (green) / "exceeds max by 5" (red)
  - "Residual: 0.01 / tolerance 0.1" (green) / "0.5 / 0.1" (red)
  - "Manifold: 0.3σ" (green) / "4.2σ" (red) / "disabled" (grey)
- [ ] Badge placed on every op card and every entry in audit log
- [ ] Manifold-distance signal behind a feature flag `plausibility.manifold_ae_enabled` (default false); when disabled, hover shows "Manifold: disabled"
- [ ] Accessibility: badge has aria-label reflecting state; not colour-only
- [ ] Fixture tests: each signal combination → expected badge colour; tooltip content correct; feature-flag off hides manifold signal
- [ ] `npm test` and `npm run build` pass

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "UI-012: plausibility badge (range + residual + manifold)"` ← hook auto-moves this file to `done/` on commit
