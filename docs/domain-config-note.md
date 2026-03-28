# Domain Config Note

The first runnable domain defaults for HypotheX-TS live in `backend/config/mvp-domain-config.json`.

This file is the canonical source for:

- active MVP chunk types
- threshold defaults for chunk scoring
- duration limits
- legal operations by chunk type
- default hard or soft constraint modes

Backend code should load it through `app.core.domain_config.load_domain_config()`. If the file is missing or malformed, the loader raises `DomainConfigError` instead of falling back silently.

Segment statistics and later chunk-scoring utilities should read threshold and duration defaults from this config rather than introducing new magic numbers in domain code.

Score-based chunk assignment should also read the ambiguity margin and active chunk vocabulary from this config so uncertain labels remain explicit and domain-controlled.

The MVP constraint engine should read per-constraint default modes from this same config, including the basic label-compatibility rule, rather than embedding hard or soft severities directly in service code.
