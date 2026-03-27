\# AGENTS.md



\## Repository guidance



\- Read `docs/planning/Rules.txt` first.

\- Then read `docs/planning/codex\_rules\_hypothe\_x\_ts.md`.

\- Before coding, read the active ticket in `tickets/`.

\- Use `docs/planning/implementation\_steps\_hypothe\_x\_ts.md` for step decomposition only.

\- Use `docs/planning/ticket\_template\_codex\_hypothe\_x\_ts.md` when creating or updating tickets.

\- Read research docs only when they are directly relevant to the active task.

\- Work one ticket at a time.

\- Do not make unrelated changes.

\- Run required tests before marking work done.



\## Project stack



\- Frontend: Vue.js

\- Backend: Flask

\- Local database: SQLite

\- ORM: SQLAlchemy



\## Data and benchmark paths



\- Canonical benchmark root: `benchmarks/`

\- Normalized datasets: `benchmarks/datasets/`

\- Raw benchmark downloads: `benchmarks/raw/`

\- Model repositories: `benchmarks/models/repos/`

\- Trained weights: `benchmarks/models/weights/`



Do not invent alternate data paths unless the active ticket explicitly requires it.



\## Dependency management



\- Whenever you add a new library, update the correct dependency manifest in the same ticket.

\- Python backend dependencies go in `backend/requirements.txt`.

\- Frontend dependencies go in `frontend/package.json`.

\- Do not import undeclared libraries.

\- After changing dependencies, run the relevant install step and verify startup/tests still work.



\## Project workflow



\- Start with `HTS-000` before feature tickets.

\- Follow ticket dependencies in order.

\- Keep route handlers thin.

\- Do not place backend business logic in frontend code.

\- Keep configuration and path handling centralized.

