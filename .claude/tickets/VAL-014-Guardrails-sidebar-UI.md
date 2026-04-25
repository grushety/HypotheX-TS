# VAL-014 — Guardrails sidebar UI component

**Status:** [ ] Done
**Depends on:** VAL-010, VAL-011, VAL-012, VAL-013

---

## Goal

Side-panel UI component that displays the 5 session-level Guardrails metrics (shape-vocab coverage, DPP diversity, validity rate, cherry-picking risk, forking-paths counter) following Lisnic et al. CHI 2025 design language: subtle by default, foregrounding only when thresholds are crossed.

**Why:** Without this component, the session-level metrics are invisible to the user. Lisnic 2025's central finding is that intervention design matters more than the underlying metric — too aggressive and users dismiss; too subtle and they ignore. The 2-D context-type × layout design space gives concrete guidance.

**How it fits:** New side panel, collapsible. Subscribes to validation event bus topics. Each metric renders as a small status row with hover-to-expand explanations. When thresholds cross, the panel border pulses once and the offending metric row foregrounds.

---

## Acceptance Criteria

- [ ] `frontend/src/components/guardrails/GuardrailsSidebar.vue` collapsible side-panel component (right-docked by default, configurable to bottom)
- [ ] 5 metric rows: `CoverageRow.vue`, `DiversityRow.vue`, `ValidityRow.vue`, `CherryPickingRow.vue`, `ForkingPathsRow.vue`
- [ ] Each row shows: metric name, current value (numeric + sparkline), traffic-light icon (green/amber/red), expandable hover explanation
- [ ] Threshold-crossing rules per metric pulled from VAL-010..013 (no hard-coded thresholds in UI)
- [ ] Threshold cross → border pulse animation (1 s, dismissable) + foregrounding of the offending row
- [ ] **Lisnic 2025 design constraints:** non-blocking; never modal; user can dismiss the pulse; user can disable individual metrics in settings
- [ ] Sparkline shows last 20 events for each metric
- [ ] Hover tooltip cites the metric's source paper (e.g. "Cherry-picking risk: TS adaptation of Hinns et al. 2026")
- [ ] aria-live='polite' on threshold-cross notifications (accessibility)
- [ ] Settings dialog: enable/disable per metric, customise thresholds, reset session counters
- [ ] Subscribes to `coverage_update`, `diversity_update`, `validity_update`, `cherry_picking_update`, `forking_paths_update` event bus topics
- [ ] Fixture tests: each row renders correctly on synthetic data; threshold-crossing triggers pulse; dismiss works; settings persist; aria-live announcement on crossing
- [ ] `npm test` and `npm run build` pass

## Definition of Done
- [ ] Run `test-writer` agent — row rendering, threshold pulse, dismiss, settings, aria
- [ ] Run `code-reviewer` agent — no blocking issues; no colour-only communication; threshold rules consumed from backend, not duplicated in UI
- [ ] `git commit -m "VAL-014: Guardrails sidebar UI component"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
