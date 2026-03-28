# Domain Config

This directory stores backend-readable configuration files that turn the shared formal contracts into runnable MVP defaults.

Current file:

- `mvp-domain-config.json`: active chunk ontology, threshold defaults, duration limits, legal operations by chunk type, and default constraint severities

Load this file through `app.core.domain_config.load_domain_config()`. Do not hard-code threshold values or legal operation mappings in business logic when the configuration layer already defines them.
