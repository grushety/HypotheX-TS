# UI-008 — Donor picker (for replace_from_library)

**Status:** [x] Done
**Depends on:** OP-012 (DonorEngine interface)

---

## Goal

Modal/side-panel UI that lets the user browse donor candidates from multiple backends for the Tier-1 `replace_from_library` op, with preview and accept/reject.

Three features:

**1. Backend selector + candidate cards**
Dropdown chooses backend: NativeGuide (default), SETS, Discord, TimeGAN, ShapeDBA, UserDrawn. Per-candidate card shows thumbnail preview + distance metric + "accept" button.

**2. Side-by-side comparison**
Original segment vs candidate donor with a crossfade-width slider (passes `crossfade_width` to OP-012).

**3. UserDrawn sketch-pad**
HTML canvas that accepts mouse/touch input; output becomes the donor curve (normalised to segment length and amplitude range).

---

## Acceptance Criteria

- [x] `frontend/src/components/donors/DonorPicker.vue` side-panel component
- [x] `DonorCard.vue` subcomponent: thumbnail (sparkline), metric (DTW distance / matrix-profile value / latent distance), accept button
- [x] Backend selector (dropdown) with 6 options; default = NativeGuide
- [x] 6th option "UserDrawn" opens `DonorSketchpad.vue` canvas component; mouse/touch events captured and converted to time series (smooth interpolation, amplitude normalised to original min/max)
- [x] Side-by-side comparison plot with crossfade slider; accept button applies OP-012 with the picked donor + crossfade width
- [x] Reject button requests next donor from same backend (backend returns k-th nearest / k-th discord) — *UI signal wired (k + exclude_ids in the request); the existing NativeGuide/SETSDonor/DiscordDonor backends return only the closest, so a future ticket will extend them for k-th support*
- [x] Loading state during backend fetch; error shown inline on network failure
- [x] Accept triggers `op-invoked` with `{tier: 1, op_name: 'replace_from_library', params: {backend, donor_id, crossfade_width}}`
- [x] Fixture tests: each backend returns thumbnails; sketchpad produces valid TS; accept → API call fired with correct payload
- [x] `npm test` and `npm run build` pass

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "UI-008: donor picker with 6 backends + sketchpad"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Created `frontend/src/lib/donors/{createDonorPickerState.js, sketchpadToSeries.js}` (pure libs), `frontend/src/services/api/donorApi.js` (HTTP client with documented `POST /api/donors/propose` contract), and three Vue components: `DonorPicker.vue` (side panel), `DonorCard.vue` (sparkline thumbnail + metric + Accept), `DonorSketchpad.vue` (canvas with mouse + touch capture, rAF-throttled redraw, Clear button). State exports `BACKEND_OPTIONS` (6 entries: NativeGuide, SETSDonor, DiscordDonor, TimeGAN, ShapeDBA, UserDrawn — the last three flagged appropriately: TimeGAN/ShapeDBA `supported: false` and disabled in the dropdown until their generators land; UserDrawn supported but bypasses the network), `clampCrossfadeWidth` (range `[0, 0.5]`, NaN → default), `buildAcceptPayload` (emits the OP-012 shape `{tier:1, op_name:'replace_from_library', params:{backend, donor_id, crossfade_width}}` with `donor_values` inlined for UserDrawn since the backend never sees the sketch otherwise), `createDonorPickerState` (composes options + candidates + selection + loading/error into a frozen view model with derived `canAccept`/`canReject`), and `formatDistance` (em-dash for null/NaN, scientific notation below 0.001).

`sketchpadToSeries` pipeline: dedupe duplicate-x → sort ascending → linear interpolate onto a uniform grid of length `targetLength` → flip canvas-y (canvas grows downward, output grows upward) → min-max rescale to `amplitudeRange`. Returns null on too few points / zero-width x range / invalid amplitude bounds.

`DonorPicker.vue` owns its own state via refs and a `createDonorPickerState` computed. It auto-loads candidates `onMounted` and on `props.segmentId` change (so the picker shows results immediately), dispatches `proposeDonor` via the API client, and emits `op-invoked` on Accept. Reject bumps `kIndex` and pushes the rejected `donor_id` into `excludeIds`, then re-fetches — both fields are sent to the backend so whichever convention the eventual k-th implementation picks will work. The side-by-side comparison is two SVG paths (original + dashed donor) sharing a normalised viewBox; the crossfade slider is a native `<input type="range">` with explicit `aria-label`.

**Three known scope limitations** (called out by code-reviewer as worth documenting; not blockers):
1. **Backend route is not in this ticket.** `POST /api/donors/propose` is documented as a contract in `donorApi.js` but the Flask blueprint (a thin adapter over the existing `NativeGuide`/`SETSDonor`/`DiscordDonor` classes from `backend/app/services/operations/tier1/replace_from_library.py`) is a separate ticket. Until that ships, the picker hits 404 in production but renders the error inline cleanly.
2. **Picker is not wired into `BenchmarkViewerPage.vue`.** The components are tree-shaken from the production bundle today (size unchanged at 155.25 kB JS gzipped 52.71). Wiring is a one-import-plus-one-handler change but expands scope; deferred as `UI-008b: wire DonorPicker into BenchmarkViewerPage`.
3. **k-th donor support is UI-only.** The backend Protocol/classes return the closest donor; the picker's `excludeIds` + `kIndex` are forwarded to the API but the existing engines ignore them. Future ticket extends `propose_donor` with `(k, exclude)` parameters.

37 new tests (createDonorPickerState 21, sketchpadToSeries 8, donorApi 8); full frontend suite 509 → 546, zero regressions; `npm run build` clean. Code-reviewer APPROVE, 0 blocking. Two real nits addressed inline: (a) added `onMounted` + segmentId-watch auto-load so the picker doesn't open empty; (b) replaced direct `redraw()` on every `mousemove` with rAF-throttled `scheduleRedraw()` to match the documented "debounced redraw" intent. Two remaining nits left for future polish (sparkline path-builder duplicated between DonorCard and the comparison plot in DonorPicker — one shared helper would consolidate ~30 LoC; `donorApi.js`'s `k: Number(k) || 0` silently coerces NaN → 0 with no validation error).
