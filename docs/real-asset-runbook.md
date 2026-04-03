# Real Asset Runbook

This runbook describes how to place, validate, and use real benchmark datasets and model artifacts in HypotheX-TS without guessing paths.

## Supported Matrix

| Dataset | Series Type | Channels | Length | Supported Model Families | Notes |
| --- | --- | ---: | ---: | --- | --- |
| GunPoint | univariate | 1 | 150 | FCN, MLP, InceptionTime | Shipped prototype smoke artifacts are available for all supported families. |
| ECG200 | univariate | 1 | 96 | FCN, MLP, InceptionTime | Shipped prototype smoke artifacts are available for all supported families. |
| Wafer | univariate | 1 | 152 | FCN, MLP, InceptionTime | Shipped prototype smoke artifacts are available for all supported families. |
| BasicMotions | multivariate | 6 | 100 | FCN, MLP, InceptionTime | Shipped prototype smoke artifacts are available for all supported families. |

## Canonical Paths

- Benchmark root: `benchmarks/`
- Dataset manifest: `benchmarks/manifests/datasets.json`
- Model manifest: `benchmarks/manifests/models.json`
- Prepared datasets: `benchmarks/datasets/<DATASET>/processed/`
- Raw copied dataset files: `benchmarks/datasets/<DATASET>/raw/`
- Raw downloaded archives: `benchmarks/raw/downloads/`
- Extracted archive contents: `benchmarks/raw/archives/`
- Reference model repos: `benchmarks/models/repos/`
- Trained or smoke model artifacts: `benchmarks/models/weights/<family>/<dataset>/`

The backend path contract is centralized in `backend/app/core/paths.py`. Do not introduce alternate asset roots unless a ticket explicitly changes the contract.

## Required Artifact Shape

Each model artifact directory must contain:

- `metadata.json`
- one checkpoint file recognized by the family adapter

Current checkpoint expectations:

- `fcn`: `best_model.keras`, `best_model.h5`, or `best_model.hdf5`
- `mlp`: `best_model.keras`, `best_model.h5`, or `best_model.hdf5`
- `inceptiontime`: `best_model.keras`, `best_model.h5`, `best_model.hdf5`, or `last_model.keras`

Current inference support is prototype-based and driven by `metadata.json`. The metadata must declare:

- `"inference_adapter": "nearest_prototype"`
- `"prototype_vectors": [...]`

## Setup Flow

1. Populate datasets with `python scripts/setup_benchmarks.py --datasets all`.
2. Inspect `benchmarks/manifests/datasets.json` and confirm the expected dataset entries are present.
3. Inspect `benchmarks/manifests/models.json` and confirm the target artifact id, family, dataset, and `input_shape`.
4. Place the artifact files under `benchmarks/models/weights/<family>/<dataset>/`.
5. Create a backend environment and install `backend/requirements.txt`.
6. Start the backend from `backend/` with `python -m flask --app run run`.
7. Start the frontend from `frontend/` with `npm install` and `npm run dev`.

## Validation Commands

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest -q backend/tests/test_real_benchmark_smoke.py
```

Frontend:

```bash
cd frontend
npm install
npm test -- --runInBand
npm run build
```

Manual API checks:

```bash
curl "http://127.0.0.1:5000/api/benchmarks/datasets"
curl "http://127.0.0.1:5000/api/benchmarks/models"
curl "http://127.0.0.1:5000/api/benchmarks/compatibility?dataset=GunPoint&artifact_id=fcn-gunpoint"
curl "http://127.0.0.1:5000/api/benchmarks/sample?dataset=GunPoint&split=test&sample_index=0"
curl "http://127.0.0.1:5000/api/benchmarks/prediction?dataset=GunPoint&artifact_id=fcn-gunpoint&split=test&sample_index=0"
```

## Smoke Expectations

- Univariate smoke paths: `GunPoint`, `ECG200`, and `Wafer` with any declared FCN, MLP, or InceptionTime artifact.
- Multivariate smoke path: `BasicMotions` with any declared FCN, MLP, or InceptionTime artifact.
- Stage order for smoke debugging: dataset registry, model registry, compatibility validation, sample load, prediction

## Common Failures

1. `Benchmark manifest was not found`
   Fix: confirm `benchmarks/manifests/datasets.json` and `benchmarks/manifests/models.json` exist and that the backend is running from the repo checkout that contains them.

2. `Model artifact directory does not exist`
   Fix: place the artifact under the exact canonical directory from `models.json`, for example `benchmarks/models/weights/fcn/GunPoint/`.

3. `Model artifact metadata.json is missing`
   Fix: add `metadata.json` to the artifact directory and ensure it declares `nearest_prototype` plus `prototype_vectors`.

4. `expects vector length ... but received ...`
   Fix: align the artifact `input_shape` and `prototype_vectors` length with the dataset series shape from `datasets.json`.

5. Compatibility says the pair is invalid
   Fix: check that the dataset name matches the artifact dataset, the channel count matches `input_shape[0]`, and the series length matches `input_shape[1]`.

6. Frontend selector loads but prediction stays unavailable
   Fix: ensure the selected artifact is compatible, the backend is reachable through the Vite `/api` proxy, and the sample has loaded successfully before requesting prediction.

7. `pytest` or `python` cannot run on the machine
   Fix: create a local Python environment under `backend/.venv` and install `backend/requirements.txt`; on this workspace, missing Python tooling has been an environment blocker rather than a code failure.

8. Frontend tests fail with `spawn EPERM`
   Fix: treat this as a local Node test-runner environment issue first; recent tickets have reproduced the same failure across the entire suite, including pre-existing tests.
