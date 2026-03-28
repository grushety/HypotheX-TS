# Shared Contracts Note

HypotheX-TS shared contracts live in the repository root under `schemas/`.

Use that directory as the canonical source for:

- time-series input payloads
- semantic segmentation payloads
- typed operation payloads
- constraint evaluation payloads
- session log export payloads

Module-specific code should map to these contracts rather than redefining them locally. Backend dataclasses, frontend API adapters, model outputs, and evaluation readers may wrap these schemas, but they should not diverge from the field names without a ticketed schema change.
