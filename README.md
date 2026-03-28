# HypotheX-TS

HypotheX-TS currently includes the first interactive MVP for semantic time-series editing:

- a Vue + Vite benchmark viewer in `frontend/`
- a Flask + SQLAlchemy backend scaffold in `backend/`
- canonical benchmark assets rooted in `benchmarks/`

## Project layout

- `frontend/` Vue application and local dev server
- `backend/` Flask application, tests, and SQLite baseline config
- `benchmarks/` benchmark datasets, raw downloads, and model repositories
- `docs/` planning and research docs
- `tickets/` implementation tickets
- `scripts/` utility scripts

## Canonical benchmark path

The single source of truth for the benchmark root is [backend/app/core/paths.py](backend/app/core/paths.py).
It defines `BENCHMARK_ROOT` as `<repo>/benchmarks` plus the canonical dataset, manifest, repo, and weight subpaths. The benchmark manifest contract lives in `benchmarks/manifests/datasets.json` and `benchmarks/manifests/models.json`, and trained model artifacts belong under `benchmarks/models/weights/<family>/<dataset>/`.

For the full operator workflow for real datasets and model artifacts, see [docs/real-asset-runbook.md](docs/real-asset-runbook.md).

The shared cross-module payload contracts for future frontend, backend, model, and evaluation work live under `schemas/`. See [schemas/README.md](schemas/README.md) and [docs/shared-contracts-note.md](docs/shared-contracts-note.md).

## Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m flask --app run run
```

The backend starts on `http://127.0.0.1:5000` and exposes `GET /api/health`.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs on `http://127.0.0.1:5173` by default and may move to the next free port if that port is already occupied.

## Frontend MVP workflow

The current frontend MVP supports:

- time-series rendering with segmentation overlay
- segment selection and highlighting
- boundary dragging
- label editing
- split, merge, and reclassify operations
- soft-constraint warnings
- interaction history
- JSON interaction-log export

## Frontend manual smoke flow

1. Start the frontend with `npm run dev`.
2. Load the benchmark viewer and confirm the ECG200 sample appears.
3. Select a segment and change its label.
4. Drag a boundary handle to update adjacent segments.
5. Run `split`, `merge`, and `reclassify` from the operation palette.
6. Trigger at least one warned action and confirm the warning panel updates.
7. Confirm the interaction history records recent actions in newest-first order.
8. Use `Export Log` in the history panel and inspect the downloaded JSON.

## Tests

```bash
cd frontend
npm test
npm run build
```

```bash
cd backend
pytest
```

For the real benchmark readiness path, run `pytest -q backend/tests/test_real_benchmark_smoke.py` after placing assets or using the shipped GunPoint smoke artifact.

## Manual verification

1. Start the frontend and walk through the frontend MVP smoke flow above.
2. Start the backend and confirm `http://127.0.0.1:5000/api/health` returns JSON with `status: "ok"`.
