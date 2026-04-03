# UI-002 — Wire uncertainty overlay and adapt-model into UI

**Status:** [ ] Done
**Depends on:** UI-001, SEG-004, SEG-005

---

## Goal

Connect the two new model endpoints to the frontend so researchers can see uncertainty
in the timeline and trigger model adaptation from accepted corrections.

Two features:

**1. Uncertainty overlay on the timeline**
After a suggestion is loaded, fetch boundary and segment uncertainty scores and render them
on the chart. Boundary uncertainty = soft glow / whisker on boundary handles.
Segment uncertainty = opacity of the segment color fill (high uncertainty → more transparent).

**2. Adapt model button**
After the user makes ≥3 manual edits or label corrections on a sample, a button
"Adapt model from corrections" appears in the model comparison panel. Clicking it
POSTs the corrected segments as a support set to `/api/benchmarks/suggestion/adapt`.
The returned `model_version_id` is shown as a small status badge ("adapted v2" etc).

No new components required — wire into existing `BenchmarkViewerPage.vue`,
`ModelComparisonPanel.vue`, and `TimelineViewer.vue`.

---

## Acceptance Criteria

- [ ] `fetchBenchmarkUncertainty(datasetName, split, sampleIndex)` added to `benchmarkApi.js`; calls `GET /api/benchmarks/suggestion/uncertainty`
- [ ] `adaptModel(sessionId, supportSegments)` added to `benchmarkApi.js`; calls `POST /api/benchmarks/suggestion/adapt`
- [ ] Uncertainty is fetched automatically after a suggestion loads (same trigger as suggestion fetch)
- [ ] Boundary uncertainty: each boundary handle in `TimelineViewer.vue` renders a faint width-scaled indicator (wider = more uncertain); purely visual, does not affect drag interaction
- [ ] Segment uncertainty: segment fill opacity in the segmentation track scales with `1 - u_seg` (certain segments are opaque, uncertain segments are more transparent); min opacity 0.35
- [ ] "Adapt model" button visible in `ModelComparisonPanel.vue` when `auditEvents` contains ≥3 edit or operation events for the current sample
- [ ] Clicking "Adapt model" shows loading state, calls `adaptModel`, then displays `model_version_id` as a badge next to the button
- [ ] Adapt errors shown inline (same pattern as suggestion errors); do not crash the panel
- [ ] Uncertainty data cleared when a new sample loads (same reset point as suggestion state)
- [ ] All existing interactions (boundary drag, label edit, accept/override suggestion, export log) still work
- [ ] No console errors or Vue warnings
- [ ] `npm test` and `npm run build` pass

## Definition of Done
- [ ] Run `test-writer` agent — new api functions tested, uncertainty state tested
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "UI-002: wire uncertainty overlay and adapt-model into UI"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this in when marking the ticket done. List files changed and one-line reason for each. -->
