# Evaluation Harness

This directory now contains the first technical evaluation pipeline for HypotheX-TS.

Current contents:

- `fixtures/` fixture-driven good and bad segmentation cases
- `io.py` fixture loading and JSON report writing
- `metrics.py` reproducible segmentation, stability, and constraint metrics
- `harness.py` report assembly
- `run_fixture_evaluation.py` CLI entry point
- `baselines.py` baseline-condition definitions for pilot comparison
- `telemetry.py` session-export telemetry validation against planned study metrics
- `pilot_readiness.py` pilot readiness report assembly
- `run_pilot_readiness_check.py` CLI entry point for baseline and telemetry checks
- `pilot-scenarios.json` first pilot scenario pack

Current supported metrics:

- macro IoU
- Boundary F1
- Covering
- over-segmentation rate
- prototype drift summary
- constraint violation rate

Current non-goals for this MVP harness:

- publication-quality figures
- dashboard visualizations
- full user-study analysis

Known approximations:

- WARI and SMS are intentionally reported as unsupported in the machine-readable output for now. The harness exposes that gap explicitly rather than shipping an undocumented approximation.

Example run:

```powershell
& .\.venv\Scripts\python.exe .\evaluation\run_fixture_evaluation.py .\evaluation\fixtures\known-good.json --output .\evaluation\reports\known-good-report.json
```

Pilot readiness run:

```powershell
& .\.venv\Scripts\python.exe .\evaluation\run_pilot_readiness_check.py --semantic-session .\evaluation\fixtures\semantic-session.json --baseline-session .\evaluation\fixtures\rule-only-baseline-session.json --scenario-pack .\evaluation\pilot-scenarios.json --output .\evaluation\reports\pilot-readiness-report.json
```
