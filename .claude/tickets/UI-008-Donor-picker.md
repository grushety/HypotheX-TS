# UI-008 — Donor picker (for replace_from_library)

**Status:** [ ] Done
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

- [ ] `frontend/src/components/donors/DonorPicker.vue` side-panel component
- [ ] `DonorCard.vue` subcomponent: thumbnail (sparkline), metric (DTW distance / matrix-profile value / latent distance), accept button
- [ ] Backend selector (dropdown) with 6 options; default = NativeGuide
- [ ] 6th option "UserDrawn" opens `DonorSketchpad.vue` canvas component; mouse/touch events captured and converted to time series (smooth interpolation, amplitude normalised to original min/max)
- [ ] Side-by-side comparison plot with crossfade slider; accept button applies OP-012 with the picked donor + crossfade width
- [ ] Reject button requests next donor from same backend (backend returns k-th nearest / k-th discord)
- [ ] Loading state during backend fetch; error shown inline on network failure
- [ ] Accept triggers `op-invoked` with `{tier: 1, op_name: 'replace_from_library', params: {backend, donor_id, crossfade_width}}`
- [ ] Fixture tests: each backend returns thumbnails; sketchpad produces valid TS; accept → API call fired with correct payload
- [ ] `npm test` and `npm run build` pass

## Definition of Done
- [ ] Run `test-writer` agent — backend selector, sketchpad input, accept/reject, crossfade slider
- [ ] Run `code-reviewer` agent — no blocking issues; backend-specific logic is in the API client, not the component
- [ ] `git commit -m "UI-008: donor picker with 6 backends + sketchpad"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this on completion. -->


---
