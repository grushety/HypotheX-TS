# HTS-000 — Initialize project scaffold and dependency baseline

**Ticket ID:** `HTS-000`  
**Title:** `Initialize Vue Flask SQLite SQLAlchemy scaffold`  
**Status:** `todo`  
**Priority:** `P0`  
**Type:** `feature`  
**Depends on:** `none`  
**Blocked by:** `none`  
**Owner:** `Codex`  
**Branch:** `hts/hts-000-project-init`

---

## 1. Goal

Create the initial HypotheX-TS project scaffold with the agreed stack:
- Vue.js frontend
- Flask backend
- SQLite database
- SQLAlchemy ORM

This ticket should establish the repo structure, dependency files, basic app startup flow, and the first health-check path between frontend and backend. It is the project bootstrap ticket that all later MVP tickets will depend on.

---

## 2. Scope

### In scope
- create frontend and backend directory structure
- initialize Vue frontend project
- initialize Flask backend project
- configure SQLite + SQLAlchemy baseline
- add dependency manifests for frontend and backend
- add a minimal backend health endpoint
- add a minimal frontend page that confirms backend reachability
- add README/setup notes for local development
- add initial `.gitignore`
- add a single source of truth for benchmark/data paths

### Out of scope
- benchmark dataset download automation
- model training
- time-series viewer
- segmentation overlay
- semantic operations
- constraint logic
- audit log
- production deployment
- authentication

Codex must not add product features under this ticket.

---

## 3. Context to Read First

Required:
- `Rules.txt`
- `docs/planning/codex_rules_hypothe_x_ts.md`
- `docs/planning/implementation_steps_hypothe_x_ts.md`
- `docs/planning/ticket_template_codex_hypothe_x_ts.md`

Task-specific:
- project notes that define benchmark/data path conventions
- any repo-level instruction file such as `AGENTS.md` if present

---

## 4. Affected Areas

### Likely files or modules
- `frontend/`
- `backend/`
- `backend/app/`
- `backend/app/models/`
- `backend/app/routes/`
- `backend/app/config.py`
- `backend/requirements.txt`
- `frontend/package.json`
- `frontend/src/`
- `shared/paths.py` or `backend/app/core/paths.py`
- `.gitignore`
- `README.md`

### Architecture layer
- [x] frontend
- [x] backend
- [x] API contract
- [x] domain logic
- [x] tests
- [x] docs

### Risk level
`medium`

Brief reason:
> This ticket sets the project foundation. Mistakes here will propagate into all later tickets, especially around dependency management, folder layout, and path conventions.

---

## 5. Inputs and Expected Outputs

### Inputs
- chosen stack: Vue.js + Flask + SQLite + SQLAlchemy
- agreed benchmark/data root
- repo root

### Expected outputs
- runnable frontend app
- runnable backend app
- backend health-check endpoint
- frontend page that can call the backend health endpoint
- dependency manifests committed to repo
- starter DB configuration using SQLite and SQLAlchemy
- documented local setup steps

---

## 6. Acceptance Criteria

- [ ] Repository has separate `frontend/` and `backend/` application roots.
- [ ] Frontend can run locally with the chosen Vue toolchain.
- [ ] Backend can run locally with Flask.
- [ ] Backend exposes a simple health endpoint such as `/api/health`.
- [ ] Frontend can call the backend health endpoint successfully in local development.
- [ ] SQLite is configured as the local development database.
- [ ] SQLAlchemy is installed and wired into the backend app factory or equivalent initialization path.
- [ ] Backend dependency file exists and includes all libraries needed by the backend scaffold.
- [ ] Frontend dependency file exists and includes all libraries needed by the frontend scaffold.
- [ ] A benchmark/data root constant or config entry exists and is documented.
- [ ] `.gitignore` excludes virtualenv, node_modules, build artifacts, local DB files, and downloaded benchmarks where appropriate.
- [ ] README contains startup instructions for frontend and backend.

---

## 7. Implementation Notes

Constraints:
- keep Flask route handlers thin
- do not place business logic in route handlers
- use SQLAlchemy as the ORM layer
- use SQLite only for local development baseline
- define one canonical benchmark/data root and reuse it
- keep frontend and backend decoupled through HTTP API boundaries
- choose a standard Vue setup that is lightweight and maintainable
- add all required libraries to the appropriate dependency manifest immediately when introducing them

Recommended initial layout:
- `frontend/`
- `backend/`
- `backend/app/`
- `backend/app/routes/`
- `backend/app/models/`
- `backend/app/services/`
- `backend/tests/`
- `frontend/src/`
- `frontend/src/components/`
- `frontend/src/views/`
- `shared/` only if truly needed; otherwise prefer backend-owned config plus frontend-local config

Known pitfalls:
- forgetting CORS setup for local frontend/backend communication
- scattering path constants across multiple files
- omitting dependency updates while adding imports
- mixing benchmark data with app runtime data

---

## 8. Verification Plan

### Required checks
- [ ] backend starts locally
- [ ] frontend starts locally
- [ ] health endpoint returns success
- [ ] frontend receives and renders backend health response
- [ ] backend tests for app startup and health endpoint
- [ ] lint or static checks if configured

### Commands
```bash
# backend
cd backend
python -m venv .venv
source .venv/bin/activate || .venv\Scripts\activate
pip install -r requirements.txt
python -m flask --app app run

# frontend
cd frontend
npm install
npm run dev

# tests
cd backend
pytest
```

### Manual verification
1. Start the Flask backend and confirm `/api/health` returns success JSON.
2. Start the Vue frontend and open the landing page.
3. Confirm the landing page can fetch and display backend health status.
4. Confirm SQLite database file is created in the documented location only if expected by the backend setup.

If a check cannot run, Codex must record why.

---

## 9. Definition of Done

- [ ] Goal is implemented.
- [ ] All acceptance criteria are satisfied.
- [ ] Required tests and checks pass.
- [ ] No blocking review issues remain.
- [ ] Docs/comments are updated if behavior changed.
- [ ] Changes are committed with the ticket ID.
- [ ] Ticket status is updated to `done`.

---

## 10. Deliverables

- project scaffold under `frontend/` and `backend/`
- backend dependency file
- frontend dependency file
- Flask app entrypoint and health route
- Vue starter page with backend connectivity check
- SQLite + SQLAlchemy baseline config
- path/config file for benchmark root
- `.gitignore`
- updated `README.md`

---

## 11. Review Checklist

### Scope review
- [ ] No time-series product features were added.
- [ ] No out-of-scope modeling logic was added.

### Architecture review
- [ ] Backend route handlers remain thin.
- [ ] Frontend contains no backend business logic.
- [ ] Config and path handling are centralized.

### Quality review
- [ ] Names match project concepts.
- [ ] Error handling is explicit for failed backend reachability.
- [ ] New setup behavior is covered by at least minimal tests.

### Contract review
- [ ] `/api/health` response shape is stable and documented.

---

## 12. Commit

### Branch naming
`hts/hts-000-project-init`

### Commit message
`HTS-000: initialize Vue Flask SQLite SQLAlchemy scaffold`

---

## 13. Notes for Codex

This ticket is the root dependency for the first MVP build.
Future tickets may assume:
- frontend exists and runs
- backend exists and runs
- SQLite + SQLAlchemy baseline exists
- one canonical data/benchmark root is defined
- dependency manifests are present and maintained
