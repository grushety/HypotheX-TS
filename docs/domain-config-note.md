# Domain Config Note

The first runnable domain defaults for HypotheX-TS live in `backend/config/mvp-domain-config.json`.

This file is the canonical source for:

- active MVP chunk types
- threshold defaults for chunk scoring
- duration limits
- legal operations by chunk type
- default hard or soft constraint modes

Backend code should load it through `app.core.domain_config.load_domain_config()`. If the file is missing or malformed, the loader raises `DomainConfigError` instead of falling back silently.
