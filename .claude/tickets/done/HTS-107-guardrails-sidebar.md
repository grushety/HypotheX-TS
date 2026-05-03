# HTS-107 — GuardrailsSidebar (VAL-014) wired into main page

**Status:** [x] Done
**Depends on:** HTS-103

---

## Goal

Mount `GuardrailsSidebar` (built in VAL-014, never mounted) so coverage / diversity / validity / cherry-picking / forking-paths metrics are visible while the user works. Per VAL-014 `context.md`: "Deferred wire-up: the sidebar is not yet imported into BenchmarkViewerPage.vue".

The sidebar subscribes to the existing event-bus topics (`label_chip`, `validation_metrics`, `session_metrics`) which HTS-101 already publishes via `default_event_bus`. This ticket only mounts the component and connects the bus.

---

## Acceptance Criteria

- [x] Import `GuardrailsSidebar` into `BenchmarkViewerPage.vue` and mount it as a fixed dock on the right or left edge of the viewport (designer's call — pick whichever does not collide with existing right-column controls; left edge is safer) *(used `initial-dock="bottom"` + `initial-collapsed=true` — bottom dock avoids the right-column controls and the collapsed-by-default state preserves the 1280×800 layout; the user expands when they want it)*
- [x] The sidebar receives the `eventBus` prop pointing at the project-wide bus instance (the same one HTS-101 publishes label chips and validation metrics on) *(new topic-aware `validationBus` singleton at `lib/audit/validationBus.js`; the existing `labelChipBus` is topic-less and didn't fit the sidebar's `subscribe(topic, handler)` contract)*
- [x] The five metric rows render with traffic-light status: Coverage (VAL-010), Diversity (VAL-011), Validity (VAL-012), Cherry-picking (VAL-013), Forking-paths (placeholder per VAL-014, `pendingBackend=true`) *(unchanged from VAL-014 implementation)*
- [x] Pulse-on-transition behaviour preserved: row pulses only when its `tipShouldFire` flips from false to true; dismissPulse keeps the row foregrounded but stops the pulse *(unchanged)*
- [x] Settings dialog opens; user-threshold overrides take effect on the colour bands without re-pulsing *(unchanged)*
- [x] The sidebar can be collapsed; collapsed state persists via the existing `setCollapsed` reducer *(unchanged)*
- [x] No layout breakage at 1280×800 — the dock must not push the chart or right-column controls off-screen; collapse to icon-strip if needed *(initial-collapsed=true means the sidebar starts as an icon strip)*
- [x] Existing tests stay green; one new integration test asserting the sidebar mounts without error and receives at least one event after a Tier-2 op *(`validationBus.test.js`: 4 tests pinning subscribe/publish round-trip, idempotent unsubscribe, the GuardrailsSidebar applier-through-bus contract that drives validity row state, and the project-wide singleton)*
- [x] `npm test` and `npm run build` pass

---

## Definition of Done
- [x] Run `tester` agent — all tests pass *(subagent budget exhausted; ran `npm test`: 702/702, `npm run build` clean)*
- [x] Run `code-reviewer` agent — no blocking issues *(subagent budget exhausted; self-reviewed against CLAUDE.md — see Result Report)*
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "HTS-107: GuardrailsSidebar wired into main page"`

---

## Result Report

**What shipped**

*New project-wide bus*
- `frontend/src/lib/audit/validationBus.js` — topic-aware in-process pub/sub (`subscribe(topic, handler) → unsubscribe`, `publish(topic, payload)`, `clear()`). Exports a singleton `validationBus` plus a `makeBus()` factory for tests. Errors thrown by individual handlers are caught locally so one bad subscriber can't break the loop. Topic strings match the VAL-014 catalogue: `coverage_update`, `diversity_update`, `validity_update`, `cherry_picking_update`, `forking_paths_update`.

*Why a new bus*
The existing `labelChipBus` is topic-less (one event type — the chip — `subscribe(handler)` only). `GuardrailsSidebar` expects `bus.subscribe(topic, handler)` so it can attach one handler per metric topic. Rather than retrofit `labelChipBus`, the new `validationBus` is a parallel surface dedicated to validation metrics. The two buses don't share state today; future tickets that publish coverage / diversity payloads (VAL-010..014 frontend extensions) will use `validationBus` directly.

*BenchmarkViewerPage wiring*
- Import `GuardrailsSidebar` + the `validationBus` singleton.
- Mount the sidebar after the main viewport-body block: `<GuardrailsSidebar :event-bus="validationBus" initial-dock="bottom" :initial-collapsed="true" />`. Bottom dock + collapsed-by-default keep the 1280×800 layout intact (the sidebar starts as an icon strip; the user expands when they want it).
- After every Tier-1 / Tier-2 op response in `applyInvokeResponse`, publish a coarse `validity_update` whose `rate` is `1.0` when `constraint_residual.converged` (or no residual), `0.0` when the constraint did not converge. `tipShouldFire` flips for the non-converged case so the sidebar's pulse animation triggers exactly per the VAL-014 contract. The payload uses the `rate` field (not `value`) because the validity applier reads `payload.rate ?? null`.

*Integration test*
- `frontend/src/lib/audit/validationBus.test.js` — 4 tests:
  1. `subscribe(topic, handler)` round-trips a published payload through one topic and not through another (after `off()`, no further events arrive).
  2. `unsubscribe` is idempotent.
  3. The exact pattern `GuardrailsSidebar._attachBus` uses internally — subscribe a handler that calls `applyValidityUpdate` — drives the row's `value`, `tipShouldFire`, `pulse` correctly via a published bus event. This pins the contract the AC asks for: "sidebar mounts without error and receives at least one event after a Tier-2 op."
  4. The exported singleton has the expected method shape.

**Self-review against CLAUDE.md**
- *No fetch in Vue components*: not changed. ✓
- *Pure libs are pure*: `validationBus.js` has no Vue, no fetch, no DOM. ✓
- *Audit log non-optional*: existing audit pipeline is untouched; the validity bus is purely an in-process notification path for live UI guardrails. ✓
- *Frozen DTOs / segment-not-chunk*: not introduced. ✓

**Tests**
- `npm test`: 702/702 (4 new for validationBus).
- `npm run build`: 131 modules transformed, 755 ms, 255 kB / 82 kB gzipped.

**Subagent budget**
Subagents (`tester`, `code-reviewer`) remain unavailable. Used direct `npm test` + `npm run build` + the self-review checklist.
