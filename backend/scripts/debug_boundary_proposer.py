"""Diagnostic script for BoundaryProposer (SEG-009).

Runs each backend (ClaSP, PELT, BOCPD) on a synthetic fixture and prints
detected boundaries together with a simple F1 score at tolerance δ.

Usage (from repo root, with venv active):
    python backend/scripts/debug_boundary_proposer.py
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from app.services.suggestion.boundary_proposer import BoundaryProposer, BoundaryProposerConfig

# ---------------------------------------------------------------------------
# Synthetic series: three regimes with known change-points
# ---------------------------------------------------------------------------

SERIES: list[float] = [0.0] * 30 + [4.0] * 30 + [-1.0] * 30
TRUE_BOUNDARIES = [30, 60]  # timestamps where each new segment starts
TOLERANCE = max(1, int(0.05 * len(SERIES)))  # 5 % of series length


def boundary_f1(
    predicted: list[int],
    true: list[int],
    tol: int,
) -> tuple[float, float, float]:
    matched_pred = set()
    matched_true = set()
    for p in predicted:
        for i, t in enumerate(true):
            if i not in matched_true and abs(p - t) <= tol:
                matched_pred.add(p)
                matched_true.add(i)
                break
    tp = len(matched_pred)
    prec = tp / len(predicted) if predicted else 0.0
    rec = tp / len(true) if true else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    return prec, rec, f1


def run_method(name: str, method: str, **kw: object) -> None:
    proposer = BoundaryProposer(
        BoundaryProposerConfig(method=method, min_segment_length=5, **kw)  # type: ignore[arg-type]
    )
    candidates = proposer.propose(SERIES)
    predicted = [c.timestamp for c in candidates]
    prec, rec, f1 = boundary_f1(predicted, TRUE_BOUNDARIES, TOLERANCE)
    print(f"\n[{name}]")
    print(f"  Detected timestamps : {predicted}")
    print(f"  True boundaries     : {TRUE_BOUNDARIES}")
    print(f"  Tolerance (tol)     : {TOLERANCE}")
    print(f"  Precision={prec:.2f}  Recall={rec:.2f}  F1={f1:.2f}")


if __name__ == "__main__":
    print("=" * 60)
    print(f"Series length: {len(SERIES)}, true boundaries: {TRUE_BOUNDARIES}")
    print(f"Regime levels: 0.0 -> 4.0 -> -1.0")
    print("=" * 60)

    run_method("PELT", "pelt")
    run_method("BOCPD (threshold=0.05)", "bocpd", bocpd_mean_run_length=25.0, bocpd_threshold=0.05)
    run_method("ClaSP (numpy fallback)", "clasp", clasp_window_len=10)

    print("\nDone.")
