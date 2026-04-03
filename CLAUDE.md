# HypotheX-TS

Human-centered XAI tool for time-series counterfactual exploration via user-defined semantic segmentation and a typed operation vocabulary.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask 3.1.0, Flask-SQLAlchemy 3.1.1 / SQLite, Flask-Cors 5.0.1, NumPy 2.4.3 |
| Backend tests | pytest 8.3.5 |
| Frontend | Vue 3.5.13, Vite 6.2.3, JavaScript ES modules (no TypeScript) |
| Frontend tests | Node built-in `--test` runner |

## Key Commands

```bash
# Backend
cd backend && source .venv/bin/activate   # Windows: .venv\Scripts\activate
flask --app app.factory run --port 5000
pytest backend/tests/ -x --tb=short

# Frontend
cd frontend && npm install && npm run dev
npm test
```

## Directory Structure

```
HypotheX-TS/
├── backend/app/
│   ├── config.py, factory.py, extensions.py
│   ├── core/        # config loading, path constants
│   ├── domain/      # pure business logic: stats, constraints, scoring
│   ├── models/      # SQLAlchemy ORM: AuditSession, AuditEvent
│   ├── routes/      # Flask blueprints: benchmarks, audit, health
│   ├── schemas/     # frozen dataclass DTOs
│   └── services/    # orchestration; suggestion/ subpackage
├── backend/config/mvp-domain-config.json
├── frontend/src/
│   ├── views/BenchmarkViewerPage.vue
│   ├── components/
│   ├── lib/                  # framework-agnostic logic
│   └── services/api/benchmarkApi.js
├── model/            # standalone model modules
├── evaluation/       # evaluation harness
└── schemas/          # shared JSON Schema contracts
```

## Architecture Rules — IMPORTANT

- **Routes are thin** — validate input, call one service, return JSON. No business logic.
- **Domain functions are pure** — no Flask, no DB, no I/O. Lives in `app/domain/`.
- **No fetch calls in Vue components** — use `frontend/src/services/api/` only.
- **Registries initialised once** in `factory.py`, not per-request.
- **`load_domain_config()` must use `@functools.lru_cache(maxsize=1)`** — called by every constraint function; reloading JSON per call is a bug.
- **Frozen dataclasses** for all DTOs — never mutable.
- **Dependency injection** in services — never instantiate dependencies inside methods.
- **The segment is the core unit** — operations are segment-bounded; counterfactual synthesis never crosses segment boundaries unless a ticket explicitly allows it.
- **Constraint status vocabulary: `PASS / WARN / FAIL / PROJECTED`** — not `ALLOW/DENY` or `soft/hard`.
- **Use `segment` everywhere, never `chunk`** — `chunk` is a legacy name; do not introduce new uses.
- **Audit log is non-optional** — every user operation must produce an AuditEvent.

## Critical Rules

- **`SECRET_KEY` must come from env var** — `"dev"` in config.py is a security bug
- **`FRONTEND_ORIGIN` must come from env var** — current hardcoded value is not overridable
- **Before any domain algorithm work** — read `.claude/skills/research-algorithms/SKILL.md`
- **Every domain function must cite its source** in the docstring (paper + equation)
- **Never delete or rewrite working tests** without explicit request
- **Always run tests after any code change**
- **Checkpoint before large refactors:** `git add -A && git commit -m "checkpoint: before <change>"`

## Git and Ticket Workflow

- Branch per ticket: `hts/HTS-NNN-short-description`; never commit to main
- Commit format: `HTS-NNN: short description` or `UI-NNN: short description` for UI-series tickets
- Tickets authored in **claude.ai desktop**, copied into `.claude/tickets/` by project owner
- Claude Code reads tickets, never creates them
- One ticket at a time — mark done before starting next
- When done: `test-writer` → `algorithm-auditor` (if domain code changed) → `api-validator` (if routes changed) → commit → update ticket status → check all done criteria → fill in `## Work Done` with files changed and one-line reason each

## Subagents (`.claude/agents/`)

- `test-writer` — write pytest or Node tests for existing code
- `algorithm-auditor` — verify implementation correctness against source + SotA web search
- `api-validator` — verify route response shape matches schema contract
- `doc-writer` — add docstrings/JSDoc; domain functions must cite source paper

## Skills (`.claude/skills/`)

- `domain-concepts` — segment formalism, operations, constraint status, audit schema. **Load before any segmentation / constraint / audit work.**
- `research-algorithms` — algorithm sources, equations, SotA status. **Load before any domain algorithm work.**
- `backend-patterns` — Flask layering, DI, frozen dataclasses, lru_cache, exception hierarchy.

## Reference Docs

- API spec: `docu/API-Spec.md`
- Known issues: `PROJECT_DOCUMENTATION.md` § Known Issues
- Domain config thresholds: `docs/domain-config-note.md`
- Tickets: `.claude/tickets/`

## Dependency Rule

When adding any library: update the manifest **in the same ticket**.
Python → `backend/requirements.txt` | JavaScript → `frontend/package.json`
