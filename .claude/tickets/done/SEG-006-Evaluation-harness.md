# SEG-006 — Segmentation model evaluation harness

**Status:** [x] Done
**Depends on:** SEG-003, SEG-004

---

## Goal

Measure the quality of the segmentation model against benchmark ground truth.
Two metrics required by the paper:

1. **Boundary F1** — precision/recall of proposed boundaries vs. ground-truth change points (tolerance window ±3
   timesteps)
2. **Label accuracy** — classification accuracy on segments where ground-truth label is known

Integrate into the existing HTS-601/602 evaluation pipeline (`evaluation/`).
Results are written to `evaluation/results/segmentation_eval.json`.

---

## Acceptance Criteria

- [ ] `evaluation/segmentation_eval.py` script: runs boundary F1 + label accuracy over all benchmark datasets with a
  test split
- [ ] `boundary_f1(proposed_boundaries, true_boundaries, tolerance=3, series_length=T) -> dict` function: returns
  `{precision, recall, f1}`; tolerance window means a proposed boundary within ±3 steps of a true boundary counts as a
  true positive
- [ ] `label_accuracy(proposed_segments, true_segments) -> float`: match segments by overlap (IoU > 0.5), count correct
  labels
- [ ] Ground-truth boundaries derived from class-change points in the benchmark label sequences (where consecutive
  samples have different class labels)
- [ ] Outputs `evaluation/results/segmentation_eval.json` with per-dataset and aggregate metrics
- [ ] Runnable as `python evaluation/segmentation_eval.py`; optional `--dataset` flag to run on a single dataset
- [ ] Smoke test: runs to completion on ECG200 and prints boundary F1 and label accuracy
- [ ] Results for baseline (heuristic encoder) and TCN encoder both recorded, so comparison is possible after SEG-003
  checkpoint is trained

## Definition of Done

- [ ] Run `test-writer` agent — unit tests for `boundary_f1` and `label_accuracy` pass
- [ ] Run `algorithm-auditor` agent — F1 formula and IoU matching correct
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "SEG-006: segmentation model evaluation harness"`
- [ ] Update Status to `[x] Done`

## Work Done

- `evaluation/segmentation_eval.py` — new script: `boundary_f1(proposed, true, tolerance=3, series_length=None)` (
  Turnbull 2007 tolerance-window F1); `label_accuracy(proposed_segs, true_segs)` (IoU > 0.5 match + label equality,
  Everingham 2010); `Segment` NamedTuple; `derive_true_boundaries` + `derive_true_segments` (group consecutive
  same-class test samples into ground-truth segments); `evaluate_dataset` (concatenates up to 50 test samples per
  univariate dataset, runs `propose_boundaries` + `PrototypeChunkClassifier`, computes both metrics); `main()` with
  `--dataset`, `--samples`, `--tolerance` CLI args; writes `evaluation/results/segmentation_eval.json` with per-dataset
  and aggregate results; records active encoder type (heuristic vs TCN) for baseline comparison
- `backend/tests/test_segmentation_eval.py` — 27 unit tests covering: `boundary_f1` (perfect match, empty both, empty
  proposed/true, tolerance boundary conditions, partial match, F1 formula, each true boundary matched once),
  `label_accuracy` (all correct, all wrong, empty inputs, IoU below/above threshold, partial correct),
  `derive_true_boundaries` (no change, single/multiple/every-sample changes), `derive_true_segments` (single run, two
  runs, alternating, no gaps in coverage)
