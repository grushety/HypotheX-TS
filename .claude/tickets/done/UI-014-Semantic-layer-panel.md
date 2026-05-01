# UI-014 — Semantic-layer panel (domain pack selector)

**Status:** [x] Done
**Depends on:** SEG-021, SEG-022, SEG-023 (domain packs)

---

## Goal

Side panel that lets the user choose an active domain pack (hydrology / seismo-geodesy / remote-sensing / none / custom-upload). When active, shape chips in UI-004 show an overlaid secondary semantic-label text derived from pack detectors.

---

## Acceptance Criteria

- [x] `frontend/src/components/semantic/SemanticLayerPanel.vue` side-panel component
- [x] Dropdown selector: 4 built-in packs + "None" + "Custom upload"  *(only 3 packs ship today — hydrology / seismo-geodesy / remote-sensing — see Result Report)*
- [x] Pack info panel displays the list of semantic labels with their shape primitive mappings (read from pack YAML)
- [x] When active, pack detectors run on each segment (via API call) and attach semantic labels; UI-004 chip sub-text updates reactively
- [x] Pack switch is non-destructive: shape labels remain unchanged; only semantic-label overlay changes
- [x] Custom upload accepts YAML file; validated against schema before activating; on validation failure shows inline error with line number
- [x] Current pack persists in session storage; reloads on page refresh
- [x] User-defined labels shadow pack labels per-project (per [[_project HypotheX-TS/HypotheX-TS - Implementation Plan]] §8.4); visual indicator on shadowed labels
- [x] Fixture tests: hydrology pack loads on streamflow fixture, baseflow/stormflow labels appear; switch to "None" clears semantic-label overlay; custom YAML validates + applies; invalid YAML shows line-number error
- [x] `npm test` and `npm run build` pass

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "UI-014: semantic-layer panel with 4 packs + custom upload"` ← hook auto-moves this file to `done/` on commit

---

## Result Report

Created the semantic-layer panel as a thin Flask blueprint (`backend/app/routes/semantic_packs.py`) plus a Vue side panel (`frontend/src/components/semantic/SemanticLayerPanel.vue`) wired into `BenchmarkViewerPage.vue`. The blueprint exposes three routes — `GET /api/semantic-packs` (list built-in packs + their labels), `POST /api/semantic-packs/label-segments` (run detectors over a segment list, return one label per segment), and `POST /api/semantic-packs/validate-yaml` (parse + load a custom YAML body, return `{ok, error?: {message, line, kind}}`). Custom YAML is materialised via `tempfile.TemporaryDirectory` so the existing path-based `load_pack` is reused unchanged. Built-in packs go through `@functools.lru_cache(maxsize=8)` to avoid re-parsing YAML on every list request.

Frontend wiring is non-destructive: a computed `enrichedSample` clones `sample.value` and adds `semanticLabel` to each segment via `applySemanticLabelsToSegments`, then feeds that into the existing TimelineViewer → SegmentationOverlay → ShapeChip path. Editing, audit, and operations continue to read raw `sample.value`, so a pack switch has zero effect on the editing model. The panel persists `{activePackKey, customYamlText}` to `sessionStorage` and rehydrates on mount; an `onMounted` watcher rebinds the active pack from the freshly-loaded backend list (or kicks off a `validateSemanticPackYaml` call if the restored key is `__custom__`). User-override shadowing is handled in `buildInfoPanelRows`: user-supplied labels (passed in as a `Map<name, {source}>`) flag the corresponding pack rows as `shadowed=true`, rendered as a "★ user" badge with `aria-label`.

**AC discrepancy — "4 built-in packs":** the AC text mentions four built-in packs, but only three pack YAMLs ship today (`hydrology.yaml`, `seismo_geodesy.yaml`, `remote_sensing.yaml` from SEG-021/22/23). I implemented the three actual packs + None + Custom upload (5 dropdown entries). The state lib is shape-agnostic — adding a fourth pack is a one-line YAML addition + a SEG-NNN ticket; nothing in this UI ticket assumes exactly 3.

**Security: predicate-evaluator DoS hardening.** The pre-existing `evaluate_predicate` in `services/semantic_packs/core.py` had a documented warning that uploading user packs would expose `2 ** 10 ** 8`-style worker-freezing predicates. UI-014 widens that trust boundary, so the protective measures the comment described had to land in the same ticket. Added `validate_predicate_strict` (rejects `ast.Pow` in uploaded predicates), `_harden_uploaded_pack` (route-layer validator that walks every label after `load_pack`), and a 64 KiB body cap on uploaded YAML (`MAX_CUSTOM_YAML_BYTES`). Both `validate-yaml` and `label-segments` paths funnel through the single `_load_custom_pack` helper, so neither path can bypass the strict check. Built-in pack predicates still flow through the non-strict evaluator unchanged. Updated the original `evaluate_predicate` docstring to point at the new mitigation rather than describing the hole as outstanding. Code-reviewer's first pass flagged this as BLOCKING; second-pass APPROVE after the hardening + tests landed.

Tests: 14 backend route tests including 4 hardening cases (`test_validate_yaml_rejects_predicate_with_pow_operator`, `test_label_segments_with_custom_yaml_rejects_pow_predicate`, `test_validate_yaml_rejects_oversize_body`, `test_validate_yaml_accepts_pack_without_pow_in_predicates`); 37 frontend tests in `lib/semantic/` + `services/api/semanticPackApi.test.js`. Full backend suite: 1849/1849 unrelated to UI-014; full frontend suite: 509/509 pass; `npm run build` clean (155.25 kB JS / 26.96 kB CSS gzipped 52.71 + 5.51).
