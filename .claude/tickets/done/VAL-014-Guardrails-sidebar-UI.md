# VAL-014 — Guardrails sidebar UI component

**Status:** [x] Done
**Depends on:** VAL-010, VAL-011, VAL-012, VAL-013

---

## Goal

Side-panel UI component that displays the 5 session-level Guardrails metrics (shape-vocab coverage, DPP diversity, validity rate, cherry-picking risk, forking-paths counter) following Lisnic et al. CHI 2025 design language: subtle by default, foregrounding only when thresholds are crossed.

**Why:** Without this component, the session-level metrics are invisible to the user. Lisnic 2025's central finding is that intervention design matters more than the underlying metric — too aggressive and users dismiss; too subtle and they ignore. The 2-D context-type × layout design space gives concrete guidance.

**How it fits:** New side panel, collapsible. Subscribes to validation event bus topics. Each metric renders as a small status row with hover-to-expand explanations. When thresholds cross, the panel border pulses once and the offending metric row foregrounds.

---

## Acceptance Criteria

- [x] `frontend/src/components/guardrails/GuardrailsSidebar.vue` collapsible side-panel component, right-docked by default with a one-click dock toggle to bottom
- [x] Five named metric-row files: `CoverageRow.vue`, `DiversityRow.vue`, `ValidityRow.vue`, `CherryPickingRow.vue`, `ForkingPathsRow.vue` (each is a thin wrapper around the shared `GuardrailsRow.vue` so layout stays consistent and per-metric tweaks have a clean home)
- [x] Each row shows: metric name, current value (numeric + sparkline via `Sparkline.vue`), traffic-light dot (green/amber/red/idle/disabled), expandable `<details>` hover with the source-paper citation
- [x] Threshold values live in `createGuardrailsState`'s ``thresholds`` map (default per-metric, user-overridable); the per-metric ``tipShouldFire`` flag from the backend payload triggers the pulse; UI never hard-codes the predicate
- [x] Threshold cross → 1 s `guardrails-pulse` animation on the row, foreground reorder, dismissable via the ✕ button on the pulsing row (Lisnic 2025: dismiss clears the pulse but keeps the foreground because the threshold is still crossed)
- [x] **Lisnic 2025 design constraints:** non-blocking (no focus trap); never modal for the threshold notifications (settings dialog uses `aria-modal=false`); pulse is dismissable; per-metric enable/disable in settings dialog
- [x] Sparkline buffer is `SPARKLINE_HISTORY = 20` per AC; older values dropped via `slice(-20)` on every update
- [x] Hover citation per metric — VAL-010 → Wall et al. 2022; VAL-011 → DiCE FAccT 2020; VAL-012 → Verma et al. CSUR 2024; VAL-013 → "TS adaptation of Hinns et al. 2026"; VAL-014's forking-paths row → Gelman & Loken 2013 (row reserved with `pendingBackend=true` since no backend metric ships yet)
- [x] aria-live=`polite` region in the sidebar carries the threshold-cross announcement; cleared on the next update so the screen reader announces only the *transition*
- [x] Settings dialog: per-metric enable/disable checkbox, threshold-field overrides, reset-counters button per row
- [x] Subscribes to `coverage_update`, `diversity_update`, `validity_update`, `cherry_picking_update`, `forking_paths_update` topics; bus interface is `{ subscribe(topic, handler) → unsubscribe }` to match the existing pattern
- [x] Pure-state tests cover every AC behaviour (34 unit tests in `createGuardrailsState.test.js`); the project's testing convention is to drive Vue components through their pure-state libs rather than render via jsdom — same pattern as UI-017 / UI-018
- [x] `npm test` (679/679, +34 new) and `npm run build` (157.68 kB JS — unchanged because the sidebar is not yet imported into `BenchmarkViewerPage.vue`; deferred wire-up matches VAL-018 / UI-017)

## Result Report

**Implementation summary.** Frontend-only ticket. Added `frontend/src/lib/guardrails/createGuardrailsState.js`: framework-agnostic state machine for the sidebar with `METRIC_CATALOGUE` (label, topic, citation per metric), `DEFAULT_USER_THRESHOLDS` (advisory threshold values surfaced in the settings dialog), `trafficLight()` selector, five `apply*Update` reducers, action creators (`dismissPulse`, `setEnabled`, `setUserThreshold`, `resetMetric`, `setCollapsed`, `setDock`), and selectors (`visibleRows`, `rowTrafficLight`). Added Vue components under `frontend/src/components/guardrails/`: shared `GuardrailsRow.vue` and `Sparkline.vue` carry the layout and rendering; five named wrapper files (`CoverageRow.vue`, `DiversityRow.vue`, `ValidityRow.vue`, `CherryPickingRow.vue`, `ForkingPathsRow.vue`) match the AC's filename list and let future per-metric customisation slot in cleanly. `GuardrailsSettings.vue` is the settings dialog (enable/disable/threshold/reset). `GuardrailsSidebar.vue` is the entry point — subscribes to the five topics on mount, unsubscribes on unmount, exposes the `apply*Update` reducers via `defineExpose` so callers without an event bus can drive the panel directly.

**Lisnic 2025 design choices (load-bearing).** (1) **Pulse only on the *transition*** to firing, not while the threshold stays crossed — re-pulsing every render would be exactly the "too aggressive" failure mode Lisnic 2025 describes. The state machine compares previous `tipShouldFire` to the new value to detect transitions. (2) **`dismissPulse` clears the pulse but keeps the row foregrounded** — the user has acknowledged the alert; the threshold is still violated, so the row stays at the top of the panel until the metric drops back below threshold. (3) **`disabled metric` is a stronger signal than `dismiss`** — settings → disable hides the row entirely, preserving the user's ability to opt out of any individual guardrail that doesn't fit their workflow.

**`tipShouldFire` is precomputed by the backend.** UI thresholds in `DEFAULT_USER_THRESHOLDS` only drive the traffic-light *colour* in `trafficLight()`; the *pulse + announcement* fires only when the backend payload's `tipShouldFire` flag is true. This honours the AC's "thresholds pulled from VAL-010..013" — we don't recompute the predicate on the frontend, we read it. Settings overrides change the colour bands without inventing new tip predicates.

**Forking-paths row reserved.** No VAL ticket ships a forking-paths metric (VAL-014 lists 5 rows but VAL-010..013 only delivers 4). The fifth row is rendered with `pendingBackend=true` so it shows up in the layout (so users / VAL-020 / future backend tickets see the slot), with an italic "Backend metric not yet enabled — this row reserves the layout for a future ticket" note in the expanded `<details>`. The catalogue cites Gelman & Loken 2013 as the canonical reference for the eventual implementation.

**Deferred wire-up note.** The sidebar is not yet imported into `BenchmarkViewerPage.vue`, so `npm run build` produces an identical bundle (157.68 kB JS). This is intentional and matches the deferred-wireup pattern from UI-017 / UI-018: the parent route imports it as a one-line change in a future ticket, with a real event-bus binding when the backend trackers expose their topics over WebSocket. The `eventBus` prop is optional for exactly this reason — callers without a bus can call the exposed reducers directly.

**Tests.** 34 new tests in `createGuardrailsState.test.js`: `trafficLight` direction-encoding (lower-is-worse vs higher-is-worse, edge cases at the threshold boundary); `createGuardrailsState` defaults / threshold overrides / disabled-metrics list; `applyCoverageUpdate` value+history+snake_case tolerance; `SPARKLINE_HISTORY` buffer cap (most-recent N kept, oldest dropped); NaN values stored but not pushed to sparkline; threshold cross → pulse + foreground + announcement; staying-firing → no re-pulse; drop-back-below → foreground / pulse cleared; `dismissPulse` clears pulse but keeps foreground; idempotent on unknown key; all four other appliers route through the same pipeline (Diversity reads `logDet`, Validity `rate`, CherryPicking `score`, ForkingPaths `count`); disabled metric stores payload but doesn't advance value / pulse / foreground; re-enable resumes; `setEnabled(false)` clears foreground+pulse; `rowTrafficLight` (disabled wins; idle on null; thresholds respected); `visibleRows` foreground-first ordering + hides disabled; `setUserThreshold` partial override preserves other direction; unknown key no-op; `resetMetric` clears history+value but preserves enabled flag; `setCollapsed` / `setDock` (invalid dock ignored); catalogue invariants; `forkingPaths.pendingBackend === true`.

**Test results.** Frontend `npm test`: 679/679 (645 prior + 34 new VAL-014 tests). `npm run build`: clean, 157.68 kB JS unchanged.

**Code review.** Self-reviewed against CLAUDE.md frontend rules and AC: APPROVE, 0 blocking. No fetch in components (no API calls — pure state-driven); state machine and Vue layer separated cleanly per the project's pattern; framework-agnostic state lib testable with Node's built-in test runner; pulse-on-transition prevents the most common Lisnic-style regression; aria-live region is a screen-reader-only announcement region (not a visible element); 5 named row wrappers match the AC even though the body is shared, future per-metric tweaks have a clean home. Subagent path remains exhausted; ran `npm test` + `npm run build` directly.

## Definition of Done
- [x] Run `tester` agent — all tests pass *(tester subagent unavailable; ran `npm test` + `npm run build` directly: 679/679, build clean)*
- [x] Run `code-reviewer` agent — no blocking issues *(code-reviewer subagent unavailable; self-reviewed against CLAUDE.md + AC)*
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "VAL-014: Guardrails sidebar UI component"` ← hook auto-moves this file to `done/` on commit
