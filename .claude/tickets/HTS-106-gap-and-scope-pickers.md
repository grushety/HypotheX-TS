# HTS-106 — GapFillPicker for `suppress` + ScopeAttributeEditor from chip context menu

**Status:** [ ] Done
**Depends on:** HTS-101

---

## Goal

Wire the two remaining UI components that open as small modals from the timeline:

1. **`GapFillPicker`** (UI-017): when the user clicks Tier-1 `suppress` and the selected segment is gap-heavy (`gapInfo.classifyGap === 'heavy'`), open `GapFillPicker`. On Apply, call `invokeOperation` with `op_name='suppress'`, `params: {strategy, ...}` per UI-017's `buildSuppressPayload`.
2. **`ScopeAttributeEditor`** (UI-018): right-click on a segment chip (in `TimelineViewer` or the segment list) opens a context menu with "Edit scope…" that opens the editor. On Save, call a backend route that updates the segment scope and triggers `RECLASSIFY_VIA_SEGMENTER` per OP-040.

For ScopeAttributeEditor, an HTTP route to update segment scope does not exist today. This ticket adds a thin one.

---

## Acceptance Criteria

### GapFillPicker
- [ ] In `BenchmarkViewerPage.vue`, when `handleOpInvoked` receives `{tier:1, op_name:'suppress'}` and the selected segment has `gapInfo.classifyGap === 'heavy'`, open `GapFillPicker` instead of the picker-pending fallback (which was the temporary HTS-101 branch)
- [ ] On Apply, call `invokeOperation` with the strategy returned by the picker
- [ ] On Cancel / Escape, no dispatch

### ScopeAttributeEditor
- [ ] New backend route `POST /api/segments/<segment_id>/scope` in a new `backend/app/routes/segments.py` accepting `{scope: {window_size, mode, reference, domain_hint}}`. Body validated by the existing `scope` shape on `DecomposedSegment`.
- [ ] Route persists the scope on the segment record (or the in-memory session segments — wherever the backend currently keeps segment state) and emits an audit event of kind `scope_updated` carrying `previousScope` + `nextScope`
- [ ] Route response: `{segment_id, scope, audit_id}`. Subsequent `decompose` / op calls read the stored scope per existing OP-030 contract.
- [ ] Optionally triggers `RECLASSIFY_VIA_SEGMENTER` via OP-040 when `triggerReclassify: true` in the payload — that is exactly the field `buildScopeUpdatePayload` already emits per UI-018
- [ ] Frontend: add `right-click` handler on each segment chip in `TimelineViewer` (and in the segment-list `<li>`) opening a small context menu `Edit scope… | (more in future)`
- [ ] On menu pick, open `ScopeAttributeEditor` modal (already accessibly built per UI-018)
- [ ] On Save, call the new `/api/segments/<id>/scope` route; on success, append an audit event reflecting the change; on failure, surface the error in the modal's inline error region
- [ ] Pytest coverage for the new route: happy path, malformed scope dict, unknown segment id (404)
- [ ] `npm test` and `npm run build` pass; `pytest` passes

---

## Definition of Done
- [ ] Run `tester` agent — all tests pass
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] Add "Result Report" in the ticket
- [ ] Add very short context for feature into `.claude/skills/context/context.md`
- [ ] Update Status to `[x] Done` and all criteria to `[x]`
- [ ] `git commit -m "HTS-106: GapFillPicker + ScopeAttributeEditor wired into main page"`
