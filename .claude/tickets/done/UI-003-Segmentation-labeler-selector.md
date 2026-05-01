# UI-003 — Segmentation labeler selector in UI

**Status:** [x] Done
**Depends on:** UI-001, SEG-007

---

## Goal

Let the researcher choose which labeling approach is used when requesting a model
suggestion: **Prototype** (current default) or **LLM (Phi-4-mini)** (SEG-007).

The selection persists for the session and is visible next to the "Get suggestion"
button so it is always clear which mode produced the current segments.

Three layers of change — backend route, API client, UI control:

**Backend:** `GET /api/benchmarks/suggestion` accepts a new optional query param
`labeler=prototype|llm` (default `prototype`). Maps to
`BoundarySuggestionService.propose(use_llm_cold_start=True/False)`.

**API client:** `fetchBenchmarkSuggestion` accepts a `labeler` argument and adds it
to the query string.

**UI:** A two-button toggle ("Prototype" / "LLM") in `ModelComparisonPanel.vue`
above the "Get suggestion" button. Selected labeler stored as `selectedLabeler` ref
in `BenchmarkViewerPage.vue` and passed through to the fetch call.
Active labeler shown as a small badge on the suggestion result card so it appears
in the audit log context.

---

## Acceptance Criteria

- [ ] `GET /api/benchmarks/suggestion?labeler=prototype` behaves identically to current behavior
- [ ] `GET /api/benchmarks/suggestion?labeler=llm` passes `use_llm_cold_start=True` to `propose()`
- [ ] Unknown `labeler` values default to `prototype` silently (no 400 error)
- [ ] `fetchBenchmarkSuggestion(datasetName, split, sampleIndex, labeler = "prototype")` passes `labeler` as query param
- [ ] `BenchmarkViewerPage.vue` has `selectedLabeler` ref defaulting to `"prototype"`
- [ ] `handleRequestSuggestion` passes `selectedLabeler` to `fetchBenchmarkSuggestion`
- [ ] `ModelComparisonPanel.vue` shows a two-button toggle: "Prototype" / "LLM (Phi-4)" above the "Get suggestion" button
- [ ] Active labeler is highlighted; inactive is muted
- [ ] Toggling emits `update-labeler` event; parent updates `selectedLabeler`
- [ ] After a suggestion loads, the labeler name appears as a small badge on the suggestion result (e.g. "via prototype" or "via LLM")
- [ ] `selectedLabeler` is reset to `"prototype"` when a new sample loads
- [ ] `SuggestionProposal.to_dict()` includes `"labeler": "prototype"|"llm"` field so it appears in the audit log export
- [ ] All existing interactions (accept/override suggestion, export log) still work
- [ ] `npm test` and `npm run build` pass
- [ ] `pytest backend/tests/ -x` passes

## Definition of Done
- [ ] Run `test-writer` agent — new route param tested, labeler toggle state tested
- [ ] Run `api-validator` agent — route response includes `labeler` field
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "UI-003: segmentation labeler selector in UI"`
- [ ] Update Status to `[x] Done`

## Work Done

- `backend/app/schemas/suggestions.py` — added `labeler: str = "prototype"` field to `SuggestionProposal`; `to_dict()` now always includes `"labeler"` key
- `backend/app/services/suggestions.py` — added `labeler: str = "prototype"` param to `propose()`; passed through to `SuggestionProposal` constructor
- `backend/app/routes/benchmarks.py` — `fetch_suggestion` reads `labeler` query param (default `"prototype"`); `labeler=llm` routes to `use_llm_cold_start=True, support_segments=None`; any other value treated as `"prototype"` silently; labeler value included in proposal
- `backend/tests/test_benchmark_routes.py` — 4 new tests: default labeler is "prototype", explicit `labeler=prototype`, `labeler=llm` returns `"labeler": "llm"` in response, unknown labeler defaults to "prototype" silently
- `frontend/src/services/api/benchmarkApi.js` — added `labeler = "prototype"` param (4th, before fetchImpl) to `fetchBenchmarkSuggestion`; included in query string
- `frontend/src/services/api/benchmarkApi.test.js` — updated existing test to pass `"prototype"` before mock; added 2 tests: labeler param in query string, default labeler=prototype
- `frontend/src/lib/viewer/createModelComparisonState.js` — added `selectedLabeler = "prototype"` and `suggestionLabeler = null` params; both passed through in returned state object
- `frontend/src/lib/viewer/createModelComparisonState.test.js` — 4 new tests: default selectedLabeler, pass-through selectedLabeler, pass-through suggestionLabeler, default suggestionLabeler null
- `frontend/src/components/comparison/ModelComparisonPanel.vue` — added two-button toggle "Prototype"/"LLM (Phi-4)" above "Load suggestion" (selected = primary style, unselected = secondary); emits `update-labeler`; added `"via LLM"/"via prototype"` badge shown when `hasProposal && suggestionLabeler`
- `frontend/src/views/BenchmarkViewerPage.vue` — added `selectedLabeler` ref (default `"prototype"`); reset in `clearSuggestionState()`; passed to `fetchBenchmarkSuggestion`; passed as `selectedLabeler` and `suggestionLabeler: suggestionPayload.value?.labeler` to `comparisonState`; added `handleUpdateLabeler()`; wired `@update-labeler` on `ModelComparisonPanel`
