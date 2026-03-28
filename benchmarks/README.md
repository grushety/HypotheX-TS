# HypotheX-TS Benchmarks

This directory stores benchmark datasets, raw downloads, prepared NumPy exports, and reference model codebases for later experiments.

## Structure

- `raw/downloads/`: original downloaded archive files.
- `raw/archives/ucr_uea/`: extracted canonical UCR/UEA archive contents.
- `datasets/<DATASET>/raw/`: dataset-specific raw train/test files copied from the archive.
- `datasets/<DATASET>/processed/`: normalized `.npy` exports for app loading.
- `models/repos/`: cloned reference repositories.
- `models/weights/<FAMILY>/<DATASET>/`: canonical location for trained model artifacts.
- `models/configs/`: reserved location for benchmark config files.
- `manifests/datasets.json`: canonical dataset manifest with repo-relative artifact paths.
- `manifests/models.json`: canonical model-family and artifact-location manifest.
- `manifests/`: generated manifest directory and setup report.

## Included In This Workspace

- Datasets: GunPoint, ECG200, Wafer, BasicMotions
- Model repos: included
- Supported model families: FCN, MLP, InceptionTime

## Smoke Test Readiness

- A repeatable univariate smoke artifact is included at `models/weights/fcn/GunPoint/`.
- This GunPoint artifact is a prototype-based system-readiness fixture for the backend smoke path, not a quality benchmark.
- The current smoke path exercises these stages in order: dataset registry, model registry, compatibility validation, sample load, prediction.
- The current multivariate prediction smoke is intentionally deferred. `BasicMotions` data is present and compatibility resolves, but no runnable artifact is shipped yet under `models/weights/fcn/BasicMotions/`, so the expected failure stage is `prediction`.

## Smoke Commands

1. Create a runnable backend Python environment with the dependencies from `backend/requirements.txt`.
2. Run `pytest -q backend/tests/test_real_benchmark_smoke.py`.
3. For the frontend shell, run `npm test -- --runInBand` and `npm run build` from `frontend/` if the local Node environment supports the test runner.

For the full placement, validation, and failure-handling workflow, see `docs/real-asset-runbook.md`.

## Next Steps

1. Run `python scripts/setup_benchmarks.py --datasets all` to populate this workspace.
2. Inspect `manifests/datasets.json`, `manifests/models.json`, and `manifests/setup_report.json`.
3. Use the exported arrays in `datasets/<DATASET>/processed/` for app integration or later training jobs.
4. Place trained weights under `models/weights/<FAMILY>/<DATASET>/` so backend loaders can resolve them through the manifest contract.
5. Add benchmark-specific training configs under `models/configs/` when training is introduced.
