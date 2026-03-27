# HypotheX-TS MVP Ticket Set

This bundle contains the first ticket set derived from the current IMPLEMENTATION-STEPS.md MVP recommendation.

Included MVP steps:
- STEP-01
- STEP-02
- STEP-03
- STEP-05
- STEP-06

## Ticket order

- **HTS-001** — Scaffold benchmark viewer page (depends on: none)
- **HTS-002** — Render time-series chart (depends on: HTS-001)
- **HTS-003** — Render segmentation overlay and labels (depends on: HTS-002)
- **HTS-004** — Add segment selection state and highlighting (depends on: HTS-003)
- **HTS-005** — Implement segment boundary edit domain logic (depends on: HTS-004)
- **HTS-006** — Add boundary drag interaction in the viewer (depends on: HTS-005)
- **HTS-007** — Add segment label editing UI (depends on: HTS-004)
- **HTS-008** — Add edit-state validation and tests (depends on: HTS-006, HTS-007)
- **HTS-009** — Create semantic operation domain layer (depends on: HTS-008)
- **HTS-010** — Implement split operation (depends on: HTS-009)
- **HTS-011** — Implement merge operation (depends on: HTS-010)
- **HTS-012** — Implement reclassify operation (depends on: HTS-009)
- **HTS-013** — Add operation palette and UI triggers (depends on: HTS-010, HTS-011, HTS-012)
- **HTS-014** — Stabilize semantic operations with tests (depends on: HTS-013)
- **HTS-015** — Build soft-constraint evaluation layer (depends on: HTS-014)
- **HTS-016** — Wire warnings into edit and operation flows (depends on: HTS-015)
- **HTS-017** — Add warning UI and explanations (depends on: HTS-016)
- **HTS-018** — Stabilize soft-constraint behavior with tests (depends on: HTS-017)
- **HTS-019** — Define audit event schema and capture hooks (depends on: HTS-018)
- **HTS-020** — Add interaction history panel (depends on: HTS-019)
- **HTS-021** — Export interaction log (depends on: HTS-020)
- **HTS-022** — Run MVP smoke pass and docs cleanup (depends on: HTS-021)