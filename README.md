# HypotheX-TS

HypotheX-TS now includes the initial MVP scaffold requested by `HTS-000`:

- `frontend/` contains a Vue + Vite client
- `backend/` contains a Flask + SQLAlchemy server using SQLite for local development
- `benchmarks/` remains the canonical benchmark/data root

## Project layout

- `frontend/` Vue application and local dev server
- `backend/` Flask application, tests, and SQLite baseline config
- `benchmarks/` benchmark datasets, raw downloads, and model repositories
- `docs/` planning and research docs
- `tickets/` implementation tickets
- `scripts/` utility scripts

## Canonical benchmark path

The single source of truth for the benchmark root is [backend/app/core/paths.py](backend/app/core/paths.py).
It defines `BENCHMARK_ROOT` as `<repo>/benchmarks`, and the backend health response exposes that path for verification.

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

The frontend dev server runs on `http://127.0.0.1:5173` and proxies `/api/*` requests to the Flask backend.

## Tests

```bash
cd backend
pytest
```

## Manual verification

1. Start the backend and confirm `http://127.0.0.1:5000/api/health` returns JSON with `status: "ok"`.
2. Start the frontend and open `http://127.0.0.1:5173`.
3. Confirm the page shows `Backend reachable` and renders the health payload.
