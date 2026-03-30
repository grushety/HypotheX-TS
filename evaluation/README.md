# Evaluation Harness

This directory now contains the first technical evaluation pipeline for HypotheX-TS.

Current contents:

- `fixtures/` fixture-driven good and bad segmentation cases
- `io.py` fixture loading and JSON report writing
- `metrics.py` reproducible segmentation, stability, and constraint metrics
- `harness.py` report assembly
- `run_fixture_evaluation.py` CLI entry point

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
