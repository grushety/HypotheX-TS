# Project Context

Running log of feature-level changes. One short paragraph per finished ticket, appended at ticket-completion time as a DoD step.

Format: `## <PREFIX>-NNN <short title>` heading, followed by 1–4 sentences explaining what changed and why a future Claude Code instance needs to know it (architectural decisions, non-obvious wiring, paper references, gotchas). Skip routine implementation details — those live in code comments.

---

## UI-015 Audit log panel extension (tiered ops)

Added `frontend/src/components/audit/AuditLogPanel.vue` and supporting lib files (`createAuditLogPanelState.js`, `labelChipBus.js`). The panel merges existing audit events with label chip events (from OP-041's `labelChipBus` pub/sub) to display columns: tier, op, segment, pre→post shape, rule_class, compensation_mode, plausibility_badge, constraint_residual. Tier is derived from `operationCatalog.js` when no chip is present. Filter date values from `datetime-local` inputs must be normalised to ISO-8601 via `new Date().toISOString()` before passing to `createAuditLogPanelState` — the lib uses `new Date()` comparison internally. The component is not yet wired into `BenchmarkViewerPage.vue`; mount it inside the `history-strip` details block when ready.
