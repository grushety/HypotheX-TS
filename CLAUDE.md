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
- **ALWAYS run `tester` agent → `code-reviewer` agent → commit `<PREFIX>-NNN: description`** when a ticket is done

## Ticket Authoring Rule

Tickets are authored in claude.ai (desktop chat) and copy-pasted by Yulia into `.claude/tickets/`.
Claude Code NEVER creates or edits ticket files.
Claude Code reads ticket files to understand the task, then implements the code.
Claude Code NEVER writes implementation code in ticket descriptions.
Tickets describe WHAT to do, not HOW — no Vue templates, no CSS blocks, no JS code snippets.
Claude Code reads the existing source files and decides the implementation itself.

## Ticket Workflow

All tasks are tracked as ticket files in `.claude/tickets/`.

- Each ticket is a markdown file: `<PREFIX>-NNN-Short-Title.md` where prefix is one of `SEG`, `OP`, `UI`, `VAL`, `HTS` — use `TICKET-TEMPLATE.md` as the base
- Branch per ticket: `hts/<prefix>-nnn-short-description`; never commit to main
- Ticket contains: problem description, goal, acceptance criteria, and a **Definition of Done** checklist
- **When you finish a ticket:** mark it done by updating `Status: [ ] Done` → `Status: [x] Done` in the ticket file, and tick all completed Acceptance Criteria and Definition of Done items
- **Do not start work without a ticket** — if something is unclear, ask before creating new files or making changes
- **One ticket at a time** — complete and mark done before starting the next
- **After finishing a ticket:** run `tester` agent, then `code-reviewer` agent, then commit: `git commit -m "<PREFIX>-NNN: short description"`
- The git hook auto-moves the ticket file to `done/` on commit
- Current open tickets: see `.claude/tickets/`

## Subagents (`.claude/agents/`)

- `test-writer` — write pytest or Node tests for existing code
- `algorithm-auditor` — verify implementation correctness against source + SotA web search
- `api-validator` — verify route response shape matches schema contract
- `doc-writer` — add docstrings/JSDoc; domain functions must cite source paper

## Skills (`.claude/skills/`)

- `domain-concepts` — segment formalism, operations, constraint status, audit schema. **Load before any segmentation / constraint / audit work.**
- `research-algorithms` — algorithm sources, equations, SotA status. **Load before any domain algorithm work.**
- `backend-patterns` — Flask layering, DI, frozen dataclasses, lru_cache, exception hierarchy.
- `context` — running log of feature-level changes; appended one short paragraph per finished ticket (DoD step).

## Reference Docs

- API spec: `docu/API-Spec.md`
- Known issues: `PROJECT_DOCUMENTATION.md` § Known Issues
- Domain config thresholds: `docs/domain-config-note.md`
- Tickets: `.claude/tickets/`

## Dependency Rule

When adding any library: update the manifest **in the same ticket**.
Python → `backend/requirements.txt` | JavaScript → `frontend/package.json`
