# HTS-107 — GuardrailsSidebar (VAL-014) wired into main page

**Status:** [ ] Done
**Depends on:** HTS-103

---

## Goal

Mount `GuardrailsSidebar` (built in VAL-014, never mounted) so coverage / diversity / validity / cherry-picking / forking-paths metrics are visible while the user works. Per VAL-014 `context.md`: "Deferred wire-up: the sidebar is not yet imported into BenchmarkViewerPage.vue".

The sidebar subscribes to the existing event-bus topics (`label_chip`, `validation_metrics`, `session_metrics`) which HTS-101 already publishes via `default_event_bus`. This ticket only mounts the component and connects the bus.

---

## Acceptance Criteria

- [ ] Import `GuardrailsSidebar` into `BenchmarkViewerPage.vue` and mount it as a fixed dock on the right or left edge of the viewport (designer's call — pick whichever does not collide with existing right-column controls; left edge is safer)
- [ ] The sidebar receives the `eventBus` prop pointing at the project-wide bus instance (the same one HTS-101 publishes label chips and validation metrics on)
- [ ] The five metric rows render with traffic-light status: Coverage (VAL-010), Diversity (VAL-011), Validity (VAL-012), Cherry-picking (VAL-013), Forking-paths (placeholder per VAL-014, `pendingBackend=true`)
- [ ] Pulse-on-transition behaviour preserved: row pulses only when its `tipShouldFire` flips from false to true; dismissPulse keeps the row foregrounded but stops the pulse
- [ ] Settings dialog opens; user-threshold overrides take effect on the colour bands without re-pulsing
- [ ] The sidebar can be collapsed; collapsed state persists via the existing `setCollapsed` reducer
- [ ] No layout breakage at 1280×800 — the dock must not push the chart or right-column controls off-screen; collapse to icon-strip if needed
- [ ] Existing tests stay green; one new integration test asserting the sidebar mounts without error and receives at least one event after a Tier-2 op
- [ ] `npm test` and `npm run build` pass

---

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "HTS-107: GuardrailsSidebar wired into main page"`
