## Stack and dependency rules

- Frontend stack: Vue.js
- Backend stack: Flask
- Local database: SQLite
- ORM: SQLAlchemy

## Data and benchmark paths

- Canonical benchmark root: `benchmarks/`
- Normalized datasets: `benchmarks/datasets/`
- Raw benchmark downloads: `benchmarks/raw/`
- Model repositories: `benchmarks/models/repos/`
- Trained weights: `benchmarks/models/weights/`

## Dependency management

- Whenever you add a new library, update the correct dependency manifest in the same ticket.
- Python backend dependencies go in `backend/requirements.txt`.
- Frontend dependencies go in `frontend/package.json`.
- Do not import undeclared libraries.
- After changing dependencies, run the relevant install step and verify startup/tests still work.
