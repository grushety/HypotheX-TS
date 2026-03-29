# HypotheX-TS — Ticket Set v1

Grouped by topic series and intended implementation order.

## Series overview

- **200-series** — foundation, formal layer, config, constraints
- **300-series** — backend state, operations, feedback, logging
- **400-series** — frontend interaction layer
- **500-series** — suggestion model v1
- **600-series** — technical evaluation and pilot readiness

## Ticket order

- `HTS-201` — Establish repository skeleton and shared schemas (`HTS-201 - Establish repository skeleton and shared schemas.md`)
- `HTS-202` — Add domain configuration and ontology registry (`HTS-202 - Add domain configuration and ontology registry.md`)
- `HTS-203` — Implement segment statistics and chunk scoring utilities (`HTS-203 - Implement segment statistics and chunk scoring utilities.md`)
- `HTS-204` — Implement score-based chunk assignment with ambiguity handling (`HTS-204 - Implement score-based chunk assignment with ambiguity handling.md`)
- `HTS-205` — Implement operation legality registry and validation helpers (`HTS-205 - Implement operation legality registry and validation helpers.md`)
- `HTS-206` — Implement core constraint engine for semantic segments (`HTS-206 - Implement core constraint engine for semantic segments.md`)
- `HTS-301` — Implement segmentation state manager and history model (`HTS-301 - Implement segmentation state manager and history model.md`)
- `HTS-302` — Implement structural segment operations (`HTS-302 - Implement structural segment operations.md`)
- `HTS-303` — Implement MVP typed value operations on semantic chunks (`HTS-303 - Implement MVP typed value operations on semantic chunks.md`)
- `HTS-304` — Add constraint feedback API contract for operation results (`HTS-304 - Add constraint feedback API contract for operation results.md`)
- `HTS-305` — Implement audit logging and session export (`HTS-305 - Implement audit logging and session export.md`)
- `HTS-401` — Build time-series timeline viewer with segmentation overlay (`HTS-401 - Build time-series timeline viewer with segmentation overlay.md`)
- `HTS-402` — Add manual segmentation editing in the timeline (`HTS-402 - Add manual segmentation editing in the timeline.md`)
- `HTS-403` — Build operation palette and model comparison panel (`HTS-403 - Build operation palette and model comparison panel.md`)
- `HTS-404` — Add session log panel and export controls (`HTS-404 - Add session log panel and export controls.md`)
- `HTS-501` — Integrate boundary proposal module for suggestion model v1 (`HTS-501 - Integrate boundary proposal module for suggestion model v1.md`)
- `HTS-502` — Build segment encoder and prototype chunk classifier (`HTS-502 - Build segment encoder and prototype chunk classifier.md`)
- `HTS-503` — Expose suggestion API and accept-override workflow (`HTS-503 - Expose suggestion API and accept-override workflow.md`)
- `HTS-504` — Implement guarded prototype updates and duration smoothing rules (`HTS-504 - Implement guarded prototype updates and duration smoothing rules.md`)
- `HTS-601` — Build technical evaluation harness and metric pipeline (`HTS-601 - Build technical evaluation harness and metric pipeline.md`)
- `HTS-602` — Prepare baseline evaluation flows and pilot telemetry validation (`HTS-602 - Prepare baseline evaluation flows and pilot telemetry validation.md`)

## Notes

- IDs start at **201** and move to **301, 401, 501, 601** for the next topic groups as requested.
- Tickets follow the uploaded Codex template.
- This is an initial implementation ticket set, not the final exhaustive backlog.