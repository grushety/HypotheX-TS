"""Calibrate shape-classifier thresholds from labeled validation data (SEG-010).

Reads labeled segment examples from a CSV, computes raw gate primitives per
class, applies robust percentiles, and writes an updated shape_thresholds.yaml.

Algorithm:
  Lower-bound thresholds (slope, per, peak, step, ctx, sign) use q=0.10 so that
  90% of true positive examples exceed the threshold.  Upper-bound thresholds
  (var, lin, trans) use q=0.90 so that 90% of true positives fall below.
  spike_max_len uses q=0.90 of spike segment lengths.

  Rationale: robust percentiles are preferred over mean ± k·std because gate
  feature distributions are right-skewed; the 10th/90th percentile gives a
  tighter, less noise-sensitive boundary than 1-sigma estimates.
  Ref: Niculescu-Mizil & Caruana (2005) ICML §3; Bevis & Brown (2014) J. Geodesy 88:283.

Usage (with project Python active, from repo root):
    python backend/scripts/calibrate_shape_thresholds.py [--dataset PATH] [--output PATH]
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import pathlib
import sys

import numpy as np

# Allow running from repo root without installing the package.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_BACKEND_DIR = _REPO_ROOT / "backend"
sys.path.insert(0, str(_BACKEND_DIR))

from app.services.suggestion.rule_classifier import (  # noqa: E402
    _theil_sen,
    _residual_to_line,
    _spectral_peaks,
    _peak_score,
    _step_magnitude,
    _transition_time,
    _context_contrast,
)

_DEFAULT_DATASET = (
    _REPO_ROOT / "benchmarks" / "datasets" / "shape_calibration" / "shape_calibration_data.csv"
)
_DEFAULT_OUTPUT = (
    _BACKEND_DIR / "app" / "services" / "suggestion" / "shape_thresholds.yaml"
)

_UNCERTAINTY_DELTA = 0.15  # fixed by design; not data-driven


def _file_checksum(path: pathlib.Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()[:16]


def compute_primitives(
    values: list[float],
    ctx_pre: list[float],
    ctx_post: list[float],
) -> dict[str, float]:
    """Compute raw gate feature values for a single labeled segment."""
    arr = np.asarray(values, dtype=np.float64)
    pre = np.asarray(ctx_pre, dtype=np.float64)
    post = np.asarray(ctx_post, dtype=np.float64)

    slope, sign_cons = _theil_sen(arr)
    arr_range = float(arr.max() - arr.min())
    slope_rel = slope * (len(arr) - 1) / (arr_range + 1e-8)
    var = float(np.var(arr))
    residual_lin = _residual_to_line(arr, slope)
    _fft_peak, acf_peak = _spectral_peaks(arr)
    z_max, _peak_w = _peak_score(arr, pre, post)
    step_mag = _step_magnitude(arr, pre, post)
    transition_frac = _transition_time(arr)
    context_con = _context_contrast(arr, pre, post)

    return {
        "abs_slope_rel": abs(slope_rel),
        "var": var,
        "acf_peak": acf_peak,
        "z_max": z_max,
        "abs_step_mag": abs(step_mag),
        "context_con": context_con,
        "sign_cons": sign_cons,
        "residual_lin": residual_lin,
        "transition_frac": transition_frac,
        "seg_len": float(len(arr)),
    }


def load_dataset(path: pathlib.Path) -> dict[str, list[dict[str, float]]]:
    """Load labeled CSV and return primitives grouped by shape label."""
    by_class: dict[str, list[dict[str, float]]] = {}
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            label = row["label"]
            values = json.loads(row["values"])
            ctx_pre = json.loads(row["ctx_pre"])
            ctx_post = json.loads(row["ctx_post"])
            prims = compute_primitives(values, ctx_pre, ctx_post)
            by_class.setdefault(label, []).append(prims)
    return by_class


def calibrate(by_class: dict[str, list[dict[str, float]]]) -> dict[str, float]:
    """Return calibrated threshold dict using robust percentiles.

    Lower-bound thresholds use q=0.10 (90% of true positives exceed this).
    Upper-bound thresholds use q=0.90 (90% of true positives fall below this).
    """

    def _q(label: str, key: str, q: float) -> float:
        vals = [p[key] for p in by_class.get(label, [])]
        if not vals:
            raise ValueError(f"No examples for class '{label}' — cannot calibrate '{key}'")
        return float(np.quantile(vals, q=q))

    return {
        "slope":          _q("trend",   "abs_slope_rel",    q=0.10),
        "var":            _q("plateau", "var",              q=0.90),
        "per":            _q("cycle",   "acf_peak",         q=0.10),
        "peak":           _q("spike",   "z_max",            q=0.10),
        "step":           _q("step",    "abs_step_mag",     q=0.10),
        "ctx":            _q("spike",   "context_con",      q=0.10),
        "sign":           _q("trend",   "sign_cons",        q=0.10),
        "lin":            _q("trend",   "residual_lin",     q=0.90),
        "trans":          _q("step",    "transition_frac",  q=0.90),
        "spike_max_len":  _q("spike",   "seg_len",          q=0.90),
        "uncertainty_delta": _UNCERTAINTY_DELTA,
    }


def write_yaml(
    thresholds: dict[str, float],
    output: pathlib.Path,
    dataset_checksum: str,
    dataset_path: pathlib.Path,
    version: str = "2.0.0",
) -> None:
    """Write calibrated thresholds to a YAML file."""
    calibration_date = datetime.date.today().isoformat()
    lines = [
        f"# Shape classifier thresholds — calibrated by SEG-010",
        f"# Dataset: {dataset_path.name}",
        f"# Run: python backend/scripts/calibrate_shape_thresholds.py",
        f"version: \"{version}\"",
        f"calibration_date: \"{calibration_date}\"",
        f"dataset_checksum: \"{dataset_checksum}\"",
        "",
        "thresholds:",
        "  # slope_rel = slope*(n-1)/range; 1.0 = perfect ramp",
        f"  slope: {thresholds['slope']:.6f}",
        "",
        "  # Variance ceiling for plateau gate",
        f"  var: {thresholds['var']:.6f}",
        "",
        "  # ACF peak value for periodicity gate (cycle gate lower bound)",
        f"  per: {thresholds['per']:.6f}",
        "",
        "  # Peak z-score for spike gate",
        f"  peak: {thresholds['peak']:.6f}",
        "",
        "  # Step magnitude (mean shift) for step gate",
        f"  step: {thresholds['step']:.6f}",
        "",
        "  # Context contrast for spike gate",
        f"  ctx: {thresholds['ctx']:.6f}",
        "",
        "  # Sign consistency (fraction of monotone steps) for trend gate",
        f"  sign: {thresholds['sign']:.6f}",
        "",
        "  # Residual-to-line ratio for trend / plateau gates",
        f"  lin: {thresholds['lin']:.6f}",
        "",
        "  # Transition time (fraction of segment in transition band) for step gate",
        f"  trans: {thresholds['trans']:.6f}",
        "",
        "  # Max spike length (samples)",
        f"  spike_max_len: {thresholds['spike_max_len']:.1f}",
        "",
        "  # Uncertainty margin: top-2 gate gap below this sets ShapeLabel.uncertain=True",
        "  # Ref: Platt (1999); Niculescu-Mizil & Caruana (2005)",
        f"  uncertainty_delta: {thresholds['uncertainty_delta']:.2f}",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dataset", type=pathlib.Path, default=_DEFAULT_DATASET,
        help="Path to labeled calibration CSV",
    )
    parser.add_argument(
        "--output", type=pathlib.Path, default=_DEFAULT_OUTPUT,
        help="Destination shape_thresholds.yaml",
    )
    args = parser.parse_args(argv)

    dataset_path: pathlib.Path = args.dataset
    output_path: pathlib.Path = args.output

    if not dataset_path.exists():
        sys.exit(f"Dataset not found: {dataset_path}")

    checksum = _file_checksum(dataset_path)
    by_class = load_dataset(dataset_path)
    thresholds = calibrate(by_class)
    write_yaml(thresholds, output_path, checksum, dataset_path)

    print(f"Calibrated thresholds written to {output_path}")
    print(f"Dataset: {dataset_path.name}  checksum={checksum}")
    for k, v in thresholds.items():
        print(f"  {k:20s} = {v:.6f}")


if __name__ == "__main__":
    main()
