import importlib
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

evaluation_baselines = importlib.import_module("evaluation.baselines")
evaluation_pilot = importlib.import_module("evaluation.pilot_readiness")
evaluation_telemetry = importlib.import_module("evaluation.telemetry")

FIXTURES_DIR = ROOT_DIR / "evaluation" / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_baseline_flow_catalog_includes_rule_only_comparison_flow():
    catalog = evaluation_baselines.build_baseline_flow_catalog()
    flow_ids = {flow.flow_id for flow in catalog}

    assert "semantic-interface" in flow_ids
    assert "rule-only-baseline" in flow_ids
    baseline_flow = next(flow for flow in catalog if flow.flow_id == "rule-only-baseline")
    assert "suggestion_* event" in baseline_flow.notes[1]


def test_telemetry_validation_reports_supported_and_missing_metrics_explicitly():
    semantic_session = load_fixture("semantic-session.json")
    report = evaluation_telemetry.validate_session_telemetry(semantic_session).to_dict()
    checks_by_id = {check["metricId"]: check for check in report["checks"]}

    assert checks_by_id["operation_diversity"]["status"] == "supported"
    assert checks_by_id["suggestion_uptake"]["status"] == "supported"
    assert checks_by_id["condition_assignment"]["status"] == "missing_fields"
    assert checks_by_id["condition_assignment"]["missingFields"] == ["conditionId"]
    assert checks_by_id["task_completion_marker"]["status"] == "missing_fields"


def test_pilot_readiness_report_compares_semantic_and_baseline_sessions():
    semantic_session = load_fixture("semantic-session.json")
    baseline_session = load_fixture("rule-only-baseline-session.json")
    scenarios = evaluation_pilot.load_pilot_scenarios(ROOT_DIR / "evaluation" / "pilot-scenarios.json")

    report = evaluation_pilot.build_pilot_readiness_report(
        semantic_session=semantic_session,
        baseline_session=baseline_session,
        scenario_pack=scenarios,
    )

    assert report["pilotScenarioPack"]["scenarioCount"] == 3
    assert report["telemetryValidation"]["conditionCoverage"]["semanticOnlyEventTypes"] == ["suggestion_accepted"]
    assert report["telemetryValidation"]["conditionCoverage"]["sharedEventTypes"] == [
        "operation_applied"
    ]
