# HTS-105 — Tier-3 panels: AlignWarpPanel + DecompositionEditor

**Status:** [ ] Done
**Depends on:** HTS-101, OP-031 (align_warp), OP-030 (decompose)

---

## Goal

Wire the two Tier-3 panel-bound ops end-to-end:

1. **`align_warp`** (multi-segment, Tier-3): when the user clicks the op in the multi-segment toolbar, open `AlignWarpPanel` (UI-009) with the selected segments. On Apply, call `invokeOperation` with `tier=3`, `op_name='align_warp'`, params `{reference_seg_id, segment_ids, method, warping_band}`.
2. **`decompose`** (Tier-3): when the user clicks the op, open `DecompositionEditor` (UI-007) as a side panel showing the current segment's `DecompositionBlob` with per-component sliders. Each slider commit dispatches a Tier-2 op via the existing HTS-101 dispatcher (e.g. `linear_rate` slider → `change_slope`); the editor re-fetches the new blob between edits.

The `decompose` flow first invokes Tier-3 `decompose` on the segment to populate the blob, then opens the editor against that blob. Reset is client-side only (no audit event).

---

## Acceptance Criteria

### AlignWarpPanel
- [ ] In `BenchmarkViewerPage.vue`, when `handleOpInvoked` receives `{tier:3, op_name:'align_warp'}` AND `tieredPaletteSelectedIds.length >= 2`, open `AlignWarpPanel` with the selected segments
- [ ] On Apply, call `invokeOperation` with the `params` payload built by UI-009's `buildAlignWarpPayload`. Result: warped values are spliced into `sample.values` per segment.
- [ ] On Cancel / Escape, close the panel without dispatching
- [ ] Approx-shape warning row (plateau/trend) renders inline; noise refusal blocks Apply with a tooltip — both per UI-009 spec

### DecompositionEditor
- [ ] When `handleOpInvoked` receives `{tier:3, op_name:'decompose'}`, first call `invokeOperation` to run `decompose` on the selected segment; the response `aggregate_result` (or a new `decomposition` field) carries the blob
- [ ] Open `DecompositionEditor` as a side panel (same column as the right-side controls, expanding over them) with the resulting blob
- [ ] Each handle slider commits to `invokeOperation` with the corresponding Tier-2 op + params per UI-007's component-key dispatch (`linear_rate/trend → change_slope`, `seasonal* → amplify_amplitude / phase_shift / change_period`, `step_at_* → scale_magnitude / shift_in_time`, `log_*/exp_*/transient_* → amplify / change_decay_constant`)
- [ ] Live preview is debounced at the existing `PREVIEW_DEBOUNCE_MS = 80`; commit only on slider release (per UI-007 contract)
- [ ] Reset clears local handle values and re-renders the original blob; emits no `op-invoked` event
- [ ] Close button returns to the main view; sample retains all committed edits

### Both
- [ ] Either panel is open at most once at a time; opening one closes the other
- [ ] Pending op state (the existing `pendingOpName` ref) is set while a backend call is in flight
- [ ] `npm test` and `npm run build` pass

---

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "HTS-105: Tier-3 panels (AlignWarp + DecompositionEditor)"`
