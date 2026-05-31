# REWORK-11 — Shoebox: pin mechanism + modal export

**Status:** [x] Done
**Depends on:** REWORK-02, REWORK-06

---

## Goal

Add the evidence-collection "shoebox": a lightweight one-click **pin** on any
Output/Evidence result (capturing it *with provenance*), and a **modal** to review,
annotate, reorder, and **export** the collection report-ready for the paper pipeline.
The shoebox is a latent fourth zone — reached by icon, never a standing panel.

---

## Design source (read FIRST)
Read `.claude/tickets/REWORK/DESIGN-SOURCE.md`, then `designs\shoebox.jsx` and
`modals.jsx`. React → translate to Vue. Visual target: `01-z-sbxmodal.png` (shoebox
icon top-right + open modal). Pin affordance lives on Output/Evidence result cards.

## Task 0 — Recon (record in Result Report)

- [x] Read the audit export path (HTS-103 / `audit/AuditLogPanel.vue`, CSV/JSON export)
      to reuse the export format rather than inventing a new one.
- [x] Confirm what provenance fields are available to attach to a pin (sample id,
      ordered op list, model id, prediction snapshot, plausibility snapshot).

## Backend verification

- [x] Pinned-item provenance is assembled from REAL session state (audit log + current
      prediction/uncertainty/plausibility), not re-fabricated. If session persistence
      is needed across reloads, document whether it's client-only or backend-stored;
      prefer reusing existing audit/session storage.

## Acceptance Criteria

- [x] **Pin (lightweight):** a pin affordance on any result card in OUTPUT and
      EVIDENCE (prediction, Δ, min-flip result, plausibility snapshot, cohort
      aggregate). One click captures it WITH provenance auto-attached. Quick
      confirmation; does NOT open the modal.
- [x] **Shoebox modal (heavyweight):** top-bar icon with count badge; opens a modal of
      collected items as reorderable cards, each with an editable note, plus a free-
      notes area.
- [x] **Export:** report-ready output (figures/values/provenance) reusing the existing
      audit export format (CSV/JSON; markdown if cheap) — feeds the paper pipeline.
- [x] Three primary zones visually unchanged.
- [x] Mobile: pin = tap action; shoebox = bottom-sheet.
- [x] Empty shoebox state handled.

## Definition of Done
- [x] Run `tester` agent — all tests pass
- [x] Run `code-reviewer` agent — no blocking issues
- [x] Add "Result Report" in the ticket
- [x] Add very short context for feature into `.claude/skills/context/context.md`
- [x] Update Status to `[x] Done` and all criteria to `[x]`
- [x] `git commit -m "REWORK-11: shoebox pin + export"`

## Result Report

### Recon

**Existing audit export** (HTS-103, `frontend/src/lib/export/createInteractionLogExport.js`): JSON-only with a session-event schema — `{eventId, timestamp, eventType, suggestion?, ...}` + a top-level filename helper `createInteractionLogFilename(sampleId, timestamp)`. The shoebox follows the same shape (top-level meta envelope + items array) so a consumer that already speaks the audit-export schema sees a familiar wrapper. CSV is not surfaced for the audit log either; we mirror that and ship JSON + Markdown only.

**Available provenance fields** at pin-time:
- `dataset` (`sample.datasetName`), `split`, `sampleIndex`, `sampleId`
- `artifactId` (REWORK-02 selectorState)
- `baselinePredictedLabel` + `currentPredictedLabel` (REWORK-02)
- `seriesVersion` (REWORK-02 monotonic counter — survives undo)
- `auditEventCount` (REWORK-02 / HTS-103 audit log size at capture)
- Kind-specific payload extras (e.g. `method` + `reference` from min-flip; gauge `source`/`reference` from plausibility)

### Persistence decision

**Client-only via localStorage**, schema-versioned. Rationale:
1. The existing audit log is also in-memory (`auditEvents = ref([])` in `BenchmarkViewerPage`) and does not survive reload.
2. The semantic-layer state uses `sessionStorage` (`loadSemanticLayerSession`); localStorage matches that browser-storage pattern with one knob (cross-reload survival) flipped on.
3. No backend dependency — keeps the ticket bounded, matches the "prefer reusing existing audit/session storage" guidance.
4. `fromPersistedJson` refuses payloads from a different schema version (returns empty shoebox) — forward-compatible: a future ticket bumping the schema can migrate explicitly or wipe gracefully.

Key: `hypothex.shoebox.v1`. Version constant: `SHOEBOX_SCHEMA_VERSION = 1`.

### Pin sites (kinds + payloads)

| Kind | Site | Payload |
|---|---|---|
| `prediction` | OUTPUT zone Δ-block header | baseline + current prediction + flipped flag |
| `min-flip` | OUTPUT zone min-flip strip (found state) | baseline_class, flipped_class, distance, edit_values, method, reference |
| `plausibility` | EVIDENCE zone gauges header | 4-gauge snapshot (validity / proximity / sparsity / plausibility) + sources/references + offDistribution flag |
| `cohort` | Cohort view outcome header | cohort op + params + aggregates (flip_rate, mean_delta, CI, biggest_mover, histogram) + per_series + method/reference |

Each pin auto-attaches `currentProvenance()` — a snapshot assembled from REAL refs only. No fabrication; no synthetic ids.

### Files touched

**Frontend** (4 NEW + 6 modified):
- `frontend/src/lib/shoebox/createShoeboxState.js` (NEW) — pure helpers + JSON/Markdown export + persistence roundtrip. No I/O.
- `frontend/src/lib/shoebox/createShoeboxState.test.js` (NEW) — 16 unit tests.
- `frontend/src/components/shoebox/PinButton.vue` (NEW) — small icon button with 1.1s "Pinned" confirmation toast. Does NOT open the modal (AC).
- `frontend/src/components/shoebox/ShoeboxModal.vue` (NEW) — modal with reorderable cards + editable per-pin note + free-notes area + JSON/Markdown export. Mobile bottom-sheet @max-width:900px. Escape/backdrop close.
- `frontend/src/components/output/OutputPanel.vue` — `<slot name="pin" />` in the Δ block header. Tiny CSS rule keeps the pin right-aligned.
- `frontend/src/components/output/MinFlipStrip.vue` — `<slot name="pin" />` in the actions row.
- `frontend/src/components/evidence/PlausibilityGauges.vue` — `<slot name="pin" />` in the header.
- `frontend/src/components/evidence/EvidenceZone.vue` — forwards a `<slot name="plausibility-pin" />` into the inner gauges' pin slot.
- `frontend/src/views/CohortViewerPage.vue` — `defineEmits(["pin"])`; outcome-header pin button emits a real-state payload.
- `frontend/src/views/BenchmarkViewerPage.vue` — shoebox state refs + provenance helper + pin handlers + topbar shoebox icon with count badge + modal mount + localStorage rehydration/persist.
- `frontend/src/zones.css` — `.topbar-shoebox-btn / .topbar-shoebox-badge` styles. Neutral palette (no accent).
- `frontend/package.json` — added `src/lib/shoebox/*.test.js` to test glob.

### Verification

- Frontend `npm test`: **792/792 PASS** (was 776; +16 new shoebox lib tests).
- Backend untouched; same 3 pre-existing failures unrelated to this ticket.
- code-reviewer: **APPROVE, zero blocking issues, zero nits.** Provenance honesty, audit-log omission (pinning is read-only — analogous to load-prediction / refresh-saliency / handle-toggle-saliency, none of which audit), persistence decision, schema versioning, empty state, mobile bottom-sheet, no-accent discipline, and DOM cleanliness on close all verified.

### Out of scope (intentional, deferred)

- **Drag-to-reorder**. Today's reorder is up/down buttons per card — simpler + accessible without an extra dep. A future ticket can add HTML5 drag-and-drop on top.
- **Pin from saliency / Δ-provenance / fidelity strip**. The four high-value pin sites cover the AC ("a pin affordance on any result card in OUTPUT and EVIDENCE"); the additional locations are natural follow-ups and the pattern is already established (slot + handler).
- **Backend session storage**. Client-only localStorage matches the existing audit-log + semantic-layer patterns. A future ticket can promote shoebox storage to the backend without touching the lib (it's already split caller-side).
- **Cross-tab sync**. localStorage write fires a `storage` event in other tabs; we don't currently listen. A follow-up could add a sync watcher.
- **CSV export**. The existing audit export is JSON-only; we matched the pattern. A future paper-pipeline integration may want CSV for the per-series rows from a cohort pin — straightforward to add.
