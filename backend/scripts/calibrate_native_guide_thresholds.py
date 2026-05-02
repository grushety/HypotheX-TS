"""Calibrate Native-Guide proximity thresholds per dataset (VAL-004).

For each training point ``x_i`` find its nearest neighbour ``x_j`` of the
opposite class under the chosen distance (DTW with Sakoe-Chiba band by
default), record that distance, and write the resulting NUN-distance
distribution + 90th percentile to a JSON cache the validator loads at
session start.

Reference:
  Delaney, Greene, Keane, "Instance-based Counterfactual Explanations for
  Time Series Classification," ICCBR 2021.

Usage (with project Python active, from repo root):

    python backend/scripts/calibrate_native_guide_thresholds.py \\
        --dataset ECG200 [--metric dtw] [--dtw-band 0.1] [--cache-dir PATH]

The script exits non-zero when calibration fails (single-class training
set, missing dataset, etc.). The output JSON file is overwritten on each
successful run; older calibrations are not preserved.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from typing import Iterable

import numpy as np

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_BACKEND_DIR = _REPO_ROOT / "backend"
sys.path.insert(0, str(_BACKEND_DIR))

from app.services.datasets import DatasetRegistry  # noqa: E402
from app.services.validation.native_guide import (  # noqa: E402
    DEFAULT_DTW_BAND,
    DEFAULT_PROXIMITY_PERCENTILE,
    METRIC_DTW,
    METRIC_EUCLIDEAN,
    METRIC_L1,
    compute_nun_distances,
    save_thresholds,
    thresholds_from_distances,
)

_METRIC_CHOICES = (METRIC_DTW, METRIC_EUCLIDEAN, METRIC_L1)


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", required=True,
        help="Dataset name registered in DatasetRegistry (e.g. ECG200).",
    )
    parser.add_argument(
        "--metric", default=METRIC_DTW, choices=_METRIC_CHOICES,
        help=f"Distance metric (default: {METRIC_DTW}).",
    )
    parser.add_argument(
        "--dtw-band", type=float, default=DEFAULT_DTW_BAND,
        help=f"Sakoe-Chiba radius as a fraction of length (default: {DEFAULT_DTW_BAND}).",
    )
    parser.add_argument(
        "--quantile", type=float, default=DEFAULT_PROXIMITY_PERCENTILE,
        help=f"Quantile to record as q90_nun (default: {DEFAULT_PROXIMITY_PERCENTILE}).",
    )
    parser.add_argument(
        "--cache-dir", default=None,
        help="Override the default validation cache directory.",
    )
    parser.add_argument(
        "--split", default="train", choices=("train", "test"),
        help="Dataset split used for calibration (default: train).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    registry = DatasetRegistry()
    loaded = registry.load_dataset(args.dataset)

    if args.split == "train":
        series = np.asarray(loaded.train_series, dtype=np.float64)
        labels = np.asarray(loaded.train_labels)
    else:
        series = np.asarray(loaded.test_series, dtype=np.float64)
        labels = np.asarray(loaded.test_labels)

    if series.shape[0] == 0:
        print(f"calibration failed: split {args.split!r} has no samples", file=sys.stderr)
        return 1

    print(
        f"Calibrating Native-Guide thresholds: dataset={args.dataset!r} "
        f"metric={args.metric!r} band={args.dtw_band} n_train={series.shape[0]} T={series.shape[1]}"
    )
    started = time.perf_counter()
    distances = compute_nun_distances(
        series, labels, metric=args.metric, dtw_band=args.dtw_band,
    )
    elapsed = time.perf_counter() - started
    print(f"  computed {len(distances)} NUN distances in {elapsed:.1f}s")

    thresholds = thresholds_from_distances(
        distances,
        metric=args.metric,
        dataset_name=args.dataset,
        quantile=args.quantile,
    )
    path = save_thresholds(thresholds, cache_dir=args.cache_dir)
    print(f"  q{int(args.quantile * 100)}_nun = {thresholds.q90_nun:.6f}")
    print(f"  wrote {path}")
    print(json.dumps({
        "dataset": args.dataset,
        "metric": args.metric,
        "n": len(distances),
        "q90_nun": thresholds.q90_nun,
        "min": float(min(distances)),
        "max": float(max(distances)),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
