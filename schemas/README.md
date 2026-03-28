# Shared Contracts

This directory is the canonical shared-contract layer for HypotheX-TS.

Future modules should reference these schemas before adding new wire formats or exported payloads:

- frontend: when defining API payload expectations or local export/import formats
- backend: when exposing route contracts or session export payloads
- model: when emitting segmentation proposals, operation suggestions, or constraint results
- evaluation: when reading exported sessions or benchmark fixtures

Schema files live at the top of this directory. Example fixtures live in `schemas/fixtures/`.

The shared schema layer also includes the machine-readable domain configuration contract in `domain-config.schema.json`, which matches the backend MVP config file under `backend/config/`.

If a later ticket needs a new contract, extend this directory instead of inventing an ad hoc payload in a module-local file.
