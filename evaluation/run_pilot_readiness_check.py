from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

pilot_readiness = importlib.import_module("evaluation.pilot_readiness")
write_evaluation_report = importlib.import_module("evaluation.io").write_evaluation_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run pilot-readiness checks against semantic and baseline session exports.")
    parser.add_argument("--semantic-session", type=Path, required=True)
    parser.add_argument("--baseline-session", type=Path, required=True)
    parser.add_argument("--scenario-pack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    semantic_session = pilot_readiness.load_json(args.semantic_session)
    baseline_session = pilot_readiness.load_json(args.baseline_session)
    scenario_pack = pilot_readiness.load_pilot_scenarios(args.scenario_pack)
    report = pilot_readiness.build_pilot_readiness_report(
        semantic_session=semantic_session,
        baseline_session=baseline_session,
        scenario_pack=scenario_pack,
    )
    write_evaluation_report(report, args.output)
    semantic_missing = sum(
        1 for check in report["telemetryValidation"]["semanticSession"]["checks"] if check["status"] != "supported"
    )
    baseline_missing = sum(
        1 for check in report["telemetryValidation"]["baselineSession"]["checks"] if check["status"] != "supported"
    )
    print(f"PILOT_OUTPUT={args.output}")
    print(f"SCENARIO_COUNT={report['pilotScenarioPack']['scenarioCount']}")
    print(f"SEMANTIC_MISSING_CHECKS={semantic_missing}")
    print(f"BASELINE_MISSING_CHECKS={baseline_missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
