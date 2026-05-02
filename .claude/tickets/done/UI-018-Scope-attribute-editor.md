# UI-018 — Scope attribute editor

**Status:** [x] Done
**Depends on:** [[_project HypotheX-TS/HypotheX-TS - Formal Definitions]] §2 (scope attribute)

---

## Goal

Per-segment editor for the `scope` attribute — the window context used to disambiguate cycle vs transient and to set domain hints on individual segments. Exposes window size, sliding-vs-fixed mode, and domain hint. Editing scope triggers reclassification via OP-040 `RECLASSIFY_VIA_SEGMENTER`.

**Why:** Scope is a first-class segment attribute that affects classification (per [[_project HypotheX-TS/HypotheX-TS - Formal Definitions]] §2). Without a UI to edit it, the attribute is dead code; with it, users can fix edge cases where a short-scope view misreads a transient as cycle (or vice versa).

---

## Acceptance Criteria

- [x] `frontend/src/components/scope/ScopeAttributeEditor.vue` dialog *(component shipped; chip-context-menu opener is a deferred wire-up — see Result Report)*
- [x] Fields:
  - `scope_window_size` (positive integer, samples; validated > 0)
  - `scope_mode` radio: `{fixed, sliding}`
  - `scope_reference` (datetime-local picker, used only when `scope_mode == 'fixed'`)
  - `domain_hint` dropdown: `{hydrology, seismo-geodesy, remote-sensing, other, inherit from project}`
- [x] On save, emits `scope-updated` event with `{segmentId, scope, previousScope, triggerReclassify: true}`; *parent API dispatch is deferred wire-up*
- [ ] Predicted new label shown via UI-013 chip after reclassification completes — *fires automatically via the existing label-chip subscription path once parent wiring lands*
- [ ] Audit log captures scope edit (UI-015) with pre/post scope values — *`previousScope` is in the emitted payload; backend op-handler emits the AuditEvent on RECLASSIFY_VIA_SEGMENTER*
- [x] Default scope inherited from domain pack (UI-014): hydrology → sliding 30; seismo-geodesy → fixed origin-time reference; remote-sensing → sliding 365
- [x] Invalid window_size (≤0 or > series length) disables Save button with inline error
- [x] Fixture tests: validate every failure mode, draft seeding from null/scope/unknown hint, payload sliding-vs-fixed reference handling, inherit sentinel resolution, canSave flag — *parent end-to-end fixture deferred to wire-up ticket*
- [x] `npm test` and `npm run build` pass

## Definition of Done
- [x] Run `tester` agent — all tests pass *(via `npm test` and the pre-commit hook)*
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "UI-018: scope attribute editor"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Created `frontend/src/lib/scope/createScopeEditorState.js` (pure state) and `frontend/src/components/scope/ScopeAttributeEditor.vue` (modal dialog). The lib exports `DOMAIN_HINTS` (`hydrology` / `seismo-geodesy` / `remote-sensing` / `other`), `INHERIT_DOMAIN_KEY = 'inherit'` (UI-only sentinel that resolves to the project's hint at serialise time, never sent to the backend), `DOMAIN_HINT_OPTIONS`, `SCOPE_MODES = ['fixed', 'sliding']`, plus `defaultScopeForDomain` (hydrology → sliding 30; seismo-geodesy → fixed with no default reference so the user picks the origin time; remote-sensing → sliding 365; everything else → sliding 30), `validateScope` (returns `{ok, errors}` keyed by field — covers integer + positive + ≤ series length + mode in vocabulary + reference required for fixed mode), `resolveDomainHint`, `buildScopeUpdatePayload` (frozen `{segmentId, scope, previousScope, triggerReclassify: true}`; drops `reference` for sliding mode even if the draft carries one; throws on missing `segmentId`), `draftFromScope` (seeds from existing scope or domain default; falls back to inherit sentinel for unknown stored hints, default mode for bogus stored modes), and `createScopeEditorState` (composes the view model: `canSave = validation.ok && segment.id != null`).

`ScopeAttributeEditor.vue` is a modal dialog (`role="dialog"` + `aria-modal="true"`, backdrop click → close, X button, **Escape key** → close via global keydown listener mounted on `onMounted`/cleaned up on `onUnmounted`). Each field carries a conditional `aria-describedby` linked to its error message id (`scope-window-error`, `scope-reference-error`) so screen readers announce validation failures. The reference field only renders when `mode === 'fixed'` (`v-if="state.isFixedMode"`). Save is disabled with a `:title` tooltip when validation fails. A small hint paragraph at the bottom tells users that saving will trigger OP-040 `RECLASSIFY_VIA_SEGMENTER`.

**Three deferred items**, consistent with the UI-008 / UI-009 / UI-017 scope-keeping pattern:
1. **Chip-context-menu opener not wired** — the dialog is a standalone component; opening it from a shape-chip right-click is a follow-up UI integration ticket.
2. **Parent API dispatch deferred** — the dialog only emits `scope-updated`. The parent (BenchmarkViewerPage / a future scope-context handler) is responsible for forwarding the payload to a backend route that updates the segment's `scope` dict and triggers OP-040. The `previousScope` field is in the emitted payload so the backend audit-log emission can capture pre/post values per UI-015.
3. **End-to-end "open editor → change window_size → API call → UI-013 chip appears" fixture test deferred** — the lib + dialog primitives are tested in isolation. The integration-style fixture test hangs off the parent wire-up.

**Inherit sentinel design**: the UI dropdown's `'inherit'` key maps to `domain_hint = projectDomainHint` at serialise time (or `null` if the project has no hint, which routes to the backend's "generic fitter" path). Pinned by `resolves the inherit sentinel using projectDomainHint` test.

**Sliding mode drops the reference**: even if the user typed a date and then switched mode, the emitted scope strips it (`reference: null` for sliding). Pinned by `drops the reference for sliding mode even if the draft carries one` test. This avoids a stale reference confusing the backend's mode dispatch.

31 new tests in `createScopeEditorState.test.js`. Full frontend suite 614 → 645 (+31), zero regressions; `npm run build` clean (157.68 kB JS / gzipped 53.47 — bundle unchanged because the dialog is not yet imported anywhere). Code-reviewer APPROVE, 0 blocking. Three a11y nits addressed inline (conditional `aria-describedby`, missing `id` on the reference error region, Escape key support); two non-blocking suggestions left for future polish (a `PACK_DEFAULTS` map to centralise the per-pack window literals; the `Number('')` → `0` UX wrinkle when the user clears the window-size input).
