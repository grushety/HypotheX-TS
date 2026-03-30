from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

evaluate_fixture_case = importlib.import_module("evaluation.harness").evaluate_fixture_case
write_evaluation_report = importlib.import_module("evaluation.io").write_evaluation_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the HypotheX-TS technical evaluation harness on a fixture.")
    parser.add_argument("fixture", type=Path, help="Path to an evaluation fixture JSON file.")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the machine-readable evaluation report JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate_fixture_case(args.fixture)
    write_evaluation_report(report.to_dict(), args.output)
    print(f"EVALUATION_FIXTURE={args.fixture}")
    print(f"EVALUATION_OUTPUT={args.output}")
    print(f"MACRO_IOU={report.metrics['segmentationQuality']['macroIoU']}")
    print(f"BOUNDARY_F1={report.metrics['segmentationQuality']['boundaryF1']['f1']}")
    print(f"CONSTRAINT_VIOLATION_RATE={report.metrics['constraintAwareness']['violationRate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
