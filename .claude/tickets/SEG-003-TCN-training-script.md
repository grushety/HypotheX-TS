# SEG-003 — Training script for TCN encoder

**Status:** [ ] Done
**Depends on:** SEG-002

---

## Goal

> **Researcher action required after this ticket:** once Claude Code marks this done, run
> `python scripts/train_tcn_encoder.py` manually. The app works without it (heuristic fallback),
> but the TCN encoder only activates once the checkpoint exists at `benchmarks/models/tcn_encoder/encoder.pt`.
> Run SEG-006 evaluation before and after training to capture the baseline vs. TCN comparison.

Provide a standalone training script that trains the `TcnSegmentEncoder` on the benchmark
datasets and saves the checkpoint to `benchmarks/models/tcn_encoder/encoder.pt`.

This is a one-off script run by the researcher, not a Flask route. It reads from
`benchmarks/datasets/` (ECG200, GunPoint, Wafer, BasicMotions), builds pseudo-labeled
segments using the existing boundary proposer + domain label templates, trains the TCN
encoder with classification loss, and writes the checkpoint.

---

## Acceptance Criteria

- [ ] Script at `scripts/train_tcn_encoder.py`, runnable as `python scripts/train_tcn_encoder.py`
- [ ] Reads all datasets under `benchmarks/datasets/` that have a `train/` split via the existing `DatasetRegistry`
- [ ] Builds training segments using `propose_boundaries` + `build_default_support_segments` to create pseudo-labeled support set (no manual labels required)
- [ ] Training loop: classification loss `L_cls = -sum(log p(y_s | s))` over support segments; Adam optimizer; configurable epochs (default 50) and lr (default 1e-3)
- [ ] Saves checkpoint to `benchmarks/models/tcn_encoder/encoder.pt` (creates dir if missing)
- [ ] Prints per-epoch loss and final accuracy on a held-out 20% split
- [ ] Optional `--epochs`, `--lr`, `--embedding-dim` CLI args via `argparse`
- [ ] Script is self-contained — no Flask app context required
- [ ] Add `benchmarks/models/tcn_encoder/` to `.gitignore` (checkpoint not committed)
- [ ] Smoke test: script runs to completion on ECG200 without error (`python scripts/train_tcn_encoder.py --epochs 2`)

## Definition of Done
- [ ] Run `test-writer` agent — unit tests for data-loading helpers pass
- [ ] Run `algorithm-auditor` agent — loss function matches paper eq. L_cls
- [ ] Run `code-reviewer` agent — no blocking issues
- [ ] `git commit -m "SEG-003: training script for TCN encoder on benchmark datasets"`
- [ ] Update Status to `[x] Done`

## Work Done
<!-- Claude Code fills this in when marking the ticket done. List files changed and one-line reason for each. -->
