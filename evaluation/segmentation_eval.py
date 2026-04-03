"""Segmentation model evaluation harness (SEG-006).

Measures segmentation quality against benchmark ground truth using two metrics:
  1. Boundary F1 — precision/recall/F1 of proposed boundaries vs. ground-truth
     class-change points with a ±3-timestep tolerance window.
  2. Label accuracy — fraction of IoU-matched (>0.5) segment pairs that share
     the same label.

Ground truth is derived by concatenating test-split samples and marking the
positions where consecutive samples have different class labels.  Each run of
consecutive same-class samples forms one ground-truth segment.

Usage:
    python evaluation/segmentation_eval.py [--dataset ECG200] [--samples N]

Results are written to evaluation/results/segmentation_eval.json.

Sources:
  - Boundary F1 with tolerance window: Turnbull (2007) "Supervised and
    Unsupervised Learning for Audio Chord Recognition", ISMIR 2007.
    Standard ±k tolerance used in audio / time-series segmentation literature.
  - IoU segment matching: Jaccard (1912) generalised to 1-D intervals;
    threshold > 0.5 follows the standard object-detection convention
    (Everingham et al. 2010, PASCAL VOC).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone
from typing import NamedTuple

_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
_EVAL_DIR = _PROJECT_ROOT / "evaluation"
_RESULTS_DIR = _EVAL_DIR / "results"
_OUTPUT_PATH = _RESULTS_DIR / "segmentation_eval.json"

# Make backend/app importable without installing as a package.
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

import numpy as np

from app.services.datasets import DatasetRegistry
from app.services.suggestion.boundary_proposal import BoundaryProposerConfig, propose_boundaries
from app.services.suggestion.prototype_classifier import (
    PrototypeChunkClassifier,
    build_default_support_segments,
)
from app.services.suggestion.segment_encoder import SegmentEncoderConfig

# Maximum number of consecutive test samples to concatenate per dataset.
# Keeps the evaluation tractable even for large datasets (e.g. Wafer).
_MAX_SAMPLES = 50


# ---------------------------------------------------------------------------
# Metric functions
# ---------------------------------------------------------------------------


def boundary_f1(
    proposed_boundaries: list[int],
    true_boundaries: list[int],
    *,
    tolerance: int = 3,
    series_length: int | None = None,  # included for API completeness; not required
) -> dict[str, float]:
    """Compute precision, recall, and F1 for proposed vs. true boundaries.

    A proposed boundary is a true positive if it falls within ±``tolerance``
    timesteps of an as-yet-unmatched true boundary.  Each true boundary can
    be matched at most once (greedy left-to-right).

    Args:
        proposed_boundaries: Sorted list of proposed boundary positions.
        true_boundaries:     Sorted list of ground-truth boundary positions.
        tolerance:           Half-width of the matching window (default 3).
        series_length:       Unused; present for a consistent public signature.

    Returns:
        Dict with keys ``precision``, ``recall``, ``f1`` (all rounded to 6 dp).

    Source: Turnbull (2007) ISMIR — standard tolerance-window boundary F1.
    """
    if not proposed_boundaries and not true_boundaries:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}

    matched_true: set[int] = set()
    true_positives = 0

    for pb in proposed_boundaries:
        match = next(
            (
                idx
                for idx, tb in enumerate(true_boundaries)
                if idx not in matched_true and abs(pb - tb) <= tolerance
            ),
            None,
        )
        if match is not None:
            matched_true.add(match)
            true_positives += 1

    precision = true_positives / max(1, len(proposed_boundaries))
    recall = true_positives / max(1, len(true_boundaries))
    f1 = (2.0 * precision * recall) / (precision + recall) if precision + recall > 0 else 0.0
    return {
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


class Segment(NamedTuple):
    """Lightweight segment descriptor used by label_accuracy."""

    start: int
    end: int
    label: str


def label_accuracy(
    proposed_segments: list[Segment],
    true_segments: list[Segment],
) -> float:
    """Compute label accuracy over IoU-matched segment pairs.

    For each true segment the best-overlapping proposed segment is found.  If
    their IoU exceeds 0.5 the pair is counted as a match; the match is correct
    when both carry the same label.

    Args:
        proposed_segments: Segments output by the model (with predicted label).
        true_segments:     Ground-truth segments (with known label).

    Returns:
        Float in [0, 1]; 0.0 if no true segment finds an IoU > 0.5 match.

    Source: IoU threshold 0.5 from Everingham et al. (2010) PASCAL VOC.
    """
    if not true_segments or not proposed_segments:
        return 0.0

    matched = 0
    correct = 0

    for ts in true_segments:
        ts_len = ts.end - ts.start + 1
        best_iou = 0.0
        best_label: str | None = None

        for ps in proposed_segments:
            overlap_start = max(ts.start, ps.start)
            overlap_end = min(ts.end, ps.end)
            if overlap_end < overlap_start:
                continue
            intersection = overlap_end - overlap_start + 1
            union = ts_len + (ps.end - ps.start + 1) - intersection
            iou = intersection / max(1, union)
            if iou > best_iou:
                best_iou = iou
                best_label = ps.label

        if best_iou > 0.5 and best_label is not None:
            matched += 1
            if best_label == ts.label:
                correct += 1

    return correct / max(1, matched) if matched > 0 else 0.0


# ---------------------------------------------------------------------------
# Ground-truth derivation helpers
# ---------------------------------------------------------------------------


def derive_true_boundaries(class_labels: list[int], sample_length: int) -> list[int]:
    """Return boundary positions where consecutive sample class labels differ.

    The boundary position is the first index of the new class run, i.e.
    ``(i + 1) * sample_length`` for each i where class_labels[i] != class_labels[i+1].

    Source: standard change-point indexing for concatenated time series.
    """
    boundaries: list[int] = []
    for i in range(len(class_labels) - 1):
        if class_labels[i] != class_labels[i + 1]:
            boundaries.append((i + 1) * sample_length)
    return boundaries


def derive_true_segments(
    class_labels: list[int],
    sample_length: int,
    label_names: list[str],
) -> list[Segment]:
    """Group consecutive same-class samples into contiguous true segments.

    Args:
        class_labels:  Integer label index for each concatenated sample.
        sample_length: Number of timesteps per sample.
        label_names:   Mapping from class index to string label name.

    Returns:
        List of Segment objects covering [0, N*sample_length - 1] without gaps.
    """
    segments: list[Segment] = []
    run_start = 0
    run_class = class_labels[0]
    for i in range(1, len(class_labels)):
        if class_labels[i] != run_class:
            label = label_names[run_class] if run_class < len(label_names) else str(run_class)
            segments.append(Segment(run_start, (i * sample_length) - 1, label))
            run_start = i * sample_length
            run_class = class_labels[i]
    # Last run.
    label = label_names[run_class] if run_class < len(label_names) else str(run_class)
    segments.append(Segment(run_start, (len(class_labels) * sample_length) - 1, label))
    return segments


# ---------------------------------------------------------------------------
# Per-dataset evaluation
# ---------------------------------------------------------------------------


def evaluate_dataset(
    dataset_name: str,
    registry: DatasetRegistry,
    classifier: PrototypeChunkClassifier,
    *,
    n_samples: int = _MAX_SAMPLES,
    tolerance: int = 3,
) -> dict:
    """Run boundary F1 + label accuracy on the first ``n_samples`` test samples.

    Returns a dict with per-dataset metrics and metadata.
    """
    dataset = registry.load_dataset(dataset_name)
    if dataset.summary.n_channels != 1:
        return {
            "dataset": dataset_name,
            "skipped": True,
            "reason": "multivariate (n_channels > 1) — not supported by default TCN config",
        }

    n = min(n_samples, dataset.test_series.shape[0])
    sample_length = int(dataset.test_series.shape[2])
    X = dataset.test_series[:n, 0, :]   # (n, T)
    y = dataset.test_labels[:n].astype(int)

    # Concatenate samples into one long series.
    series_1d = X.flatten().tolist()  # length = n * T

    # Ground truth.
    true_boundaries = derive_true_boundaries(y.tolist(), sample_length)
    true_segs = derive_true_segments(
        y.tolist(), sample_length, list(dataset.summary.classes)
    )

    # Proposed segmentation via boundary proposer.
    bp_config = BoundaryProposerConfig()
    proposal = propose_boundaries(series_1d, bp_config)

    # Extract raw boundary positions.
    proposed_boundaries = [
        seg.endIndex + 1
        for seg in proposal.provisionalSegments[:-1]
    ]

    # Classify segments (requires support prototypes).
    support = build_default_support_segments(classifier.active_labels)
    prototypes = classifier.build_prototypes(support)

    proposed_segs: list[Segment] = []
    for ps in proposal.provisionalSegments:
        from app.services.suggestion.segment_encoder import slice_series  # noqa: PLC0415
        seg_values = slice_series(series_1d, ps.startIndex, ps.endIndex)
        try:
            clf = classifier.classify_segment(seg_values, prototypes=prototypes)
            label = clf.label
        except Exception:  # noqa: BLE001
            label = "unknown"
        proposed_segs.append(Segment(ps.startIndex, ps.endIndex, label))

    bf1 = boundary_f1(proposed_boundaries, true_boundaries, tolerance=tolerance)
    la = label_accuracy(proposed_segs, true_segs)

    return {
        "dataset": dataset_name,
        "skipped": False,
        "n_samples_used": n,
        "series_length": n * sample_length,
        "n_true_boundaries": len(true_boundaries),
        "n_proposed_boundaries": len(proposed_boundaries),
        "n_proposed_segments": len(proposed_segs),
        "boundary_f1": bf1,
        "label_accuracy": round(la, 6),
        "label_accuracy_note": (
            "Compares semantic labels (trend/plateau/…) against dataset class labels; "
            "near-zero is expected and does not indicate model failure."
        ),
    }


# ---------------------------------------------------------------------------
# Aggregate helpers
# ---------------------------------------------------------------------------


def _aggregate(results: list[dict]) -> dict:
    """Compute mean metrics over non-skipped datasets."""
    active = [r for r in results if not r.get("skipped")]
    if not active:
        return {}
    prec = sum(r["boundary_f1"]["precision"] for r in active) / len(active)
    rec = sum(r["boundary_f1"]["recall"] for r in active) / len(active)
    f1 = sum(r["boundary_f1"]["f1"] for r in active) / len(active)
    la = sum(r["label_accuracy"] for r in active) / len(active)
    return {
        "n_datasets": len(active),
        "mean_boundary_precision": round(prec, 6),
        "mean_boundary_recall": round(rec, 6),
        "mean_boundary_f1": round(f1, 6),
        "mean_label_accuracy": round(la, 6),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run segmentation model evaluation on benchmark datasets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Evaluate a single dataset by name (default: all).",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=_MAX_SAMPLES,
        help="Max consecutive test samples to concatenate per dataset.",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=3,
        help="Tolerance window (±timesteps) for boundary matching.",
    )
    args = parser.parse_args()

    print("Loading dataset registry …")
    registry = DatasetRegistry()

    encoder_config = SegmentEncoderConfig()
    classifier = PrototypeChunkClassifier(encoder_config=encoder_config)

    # Detect which encoder is active.
    try:
        from app.services.suggestion.tcn_encoder import load_tcn_encoder  # noqa: PLC0415

        tcn = load_tcn_encoder()
        encoder_type = "tcn" if tcn is not None else "heuristic"
    except Exception:  # noqa: BLE001
        encoder_type = "heuristic"

    print(f"Active encoder: {encoder_type}\n")

    if args.dataset:
        dataset_names = [args.dataset]
    else:
        dataset_names = [s.name for s in registry.list_datasets()]

    results: list[dict] = []
    for name in dataset_names:
        print(f"  Evaluating {name} …")
        result = evaluate_dataset(
            name,
            registry,
            classifier,
            n_samples=args.samples,
            tolerance=args.tolerance,
        )
        results.append(result)
        if result.get("skipped"):
            print(f"    SKIPPED: {result['reason']}")
        else:
            f1 = result["boundary_f1"]["f1"]
            la = result["label_accuracy"]
            print(f"    boundary_f1={f1:.4f}  label_accuracy={la:.4f}")

    aggregate = _aggregate(results)
    print(f"\nAggregate ({aggregate.get('n_datasets', 0)} datasets):")
    print(f"  mean_boundary_f1   = {aggregate.get('mean_boundary_f1', 0):.4f}")
    print(f"  mean_label_accuracy = {aggregate.get('mean_label_accuracy', 0):.4f}")

    report = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "encoder_type": encoder_type,
        "boundary_tolerance": args.tolerance,
        "max_samples_per_dataset": args.samples,
        "per_dataset": results,
        "aggregate": aggregate,
    }

    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nResults written to {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
