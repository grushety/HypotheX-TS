"""Training script for PrototypeShapeClassifier (SEG-011).

Computes L2-normalised prototypes from REAL user-corrected support segments
and serialises them to a JSON file for production use.

WHY THIS SCRIPT REJECTS SYNTHETIC DATA — SEG-002 RETROSPECTIVE
===============================================================
The previous TCN (SEG-002) was trained on pseudo-labels generated from
synthetic prototype templates (hand-crafted canonical shapes per class).
Post-training evaluation showed no improvement over the heuristic encoder:
accuracy and confusion patterns were identical.

Root cause: the synthetic templates are derived from the same heuristic that
produces the pseudo-labels.  The training loop is circular:
  - templates → pseudo-labels → encoder trained to reproduce pseudo-labels
  - encoder output ≈ heuristic output  (no learning occurred)

Fix: prototypes must come exclusively from *real* user corrections
(provenance='user') that encode human segmentation intent.  Synthetic
segments (provenance='synthetic', 'template', etc.) are rejected here and
inside PrototypeShapeClassifier.fit_prototypes() to make the boundary
explicit and auditable.

Usage
-----
python -m backend.scripts.train_prototype_classifier \\
    path/to/support_segments.json \\
    --output benchmarks/models/prototypes/shape_prototypes.json

Input JSON schema
-----------------
[
  {
    "shape_label": "trend",
    "values": [0.0, 0.05, 0.10, ...],
    "provenance": "user"
  },
  ...
]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute PrototypeShapeClassifier prototypes from user-corrected segments.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "input_json",
        type=pathlib.Path,
        help="JSON file: list of {shape_label, values, provenance} objects.",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("benchmarks/models/prototypes/shape_prototypes.json"),
        help="Destination JSON path for serialised prototypes.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Softmax temperature τ for classification (default: 0.1).",
    )
    args = parser.parse_args()

    try:
        raw_segments = json.loads(args.input_json.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: Input file not found: {args.input_json}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR: Input file is not valid JSON: {exc}", file=sys.stderr)
        return 1

    if not isinstance(raw_segments, list):
        print("ERROR: Input JSON must be a list of support segment objects.", file=sys.stderr)
        return 1

    from app.services.suggestion.prototype_classifier import (  # noqa: PLC0415
        PrototypeClassifierError,
        PrototypeShapeClassifier,
        SupportSegment,
    )

    support_segments: list[SupportSegment] = []
    for i, raw in enumerate(raw_segments):
        if not isinstance(raw, dict):
            print(f"ERROR: Segment {i} is not a JSON object.", file=sys.stderr)
            return 1
        provenance = str(raw.get("provenance", "user"))
        if provenance != "user":
            print(
                f"ERROR: Segment {i} (label='{raw.get('shape_label')}') has "
                f"provenance='{provenance}'. Only provenance='user' is accepted.\n"
                f"Synthetic prototypes are rejected — see SEG-002 retrospective "
                f"at the top of this file.",
                file=sys.stderr,
            )
            return 1
        support_segments.append(
            SupportSegment(
                shape_label=str(raw.get("shape_label", "")),
                values=list(raw.get("values", [])),
                provenance=provenance,
            )
        )

    if not support_segments:
        print("ERROR: No support segments found in input file.", file=sys.stderr)
        return 1

    classifier = PrototypeShapeClassifier(temperature=args.temperature)
    try:
        classifier.fit_prototypes(support_segments)
    except PrototypeClassifierError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    output_data = {
        "temperature": args.temperature,
        "shape_labels": list(classifier.SHAPE_LABELS),
        "prototypes": {
            label: proto.tolist()
            for label, proto in classifier._prototypes.items()
        },
        "n_support_per_class": {
            label: sum(1 for s in support_segments if s.shape_label == label)
            for label in classifier._prototypes
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output_data, indent=2), encoding="utf-8")

    fitted_labels = sorted(classifier._prototypes)
    print(f"Prototypes saved to {args.output}")
    print(f"Fitted classes ({len(fitted_labels)}): {fitted_labels}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
