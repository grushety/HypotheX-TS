# UI-011 — Compensation-mode selector

**Status:** [ ] Done
**Depends on:** OP-051

---

## Goal

Per-op dropdown / segmented-control selector for compensation mode `{naive, local, coupled}`. Default chosen per domain hint (`local` for hydrology, `coupled` for geodesy, `naive` otherwise).

**Why:** The compensation-mode selector is the **atomic novelty** of the conservation contribution (per [[_project HypotheX-TS/HypotheX-TS - Originality Assessment]]). It must be surfaced in the UI per-op, not hidden in a global settings page.

---

## Acceptance Criteria

- [ ] `frontend/src/components/constraints/CompensationModeSelector.vue` segmented control with 3 buttons (naive / local / coupled)
- [ ] Component placed inline on every op card that triggers a conservation-affecting edit (OP-020..026 Tier-2 + OP-032 Tier-3)
- [ ] Tooltip on each mode:
  - naive: "Report residual; do not adjust"
  - local: "Adjust within this segment only"
  - coupled: "Adjust across all segments via conservation coupling"
- [ ] Default per active domain pack:
  - hydrology → local
  - seismo-geodesy → coupled
  - remote-sensing → local
  - other / no pack → naive
- [ ] Required (gates op execution) for Plateau/Trend/Step/Transient ops in hydrology and seismo-geodesy domains; optional elsewhere
- [ ] Selection persists per-op in audit log via OP-041 chip
- [ ] Fixture tests: default selection per domain; selector change triggers UI-010 budget-bar update; audit log records selection
- [ ] `npm test` and `npm run build` pass

## Definition of Done
- [ ] Run `test-writer` agent — default selection per domain, change propagation, audit recording
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "UI-011: compensation-mode selector (naive/local/coupled)"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
