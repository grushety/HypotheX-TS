from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .baselines import build_baseline_flow_catalog
from .telemetry import compare_condition_event_coverage, validate_session_telemetry


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_pilot_scenarios(path: str | Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    scenarios = payload.get("scenarios", [])
    if not isinstance(scenarios, list):
        raise ValueError("Pilot scenario pack must contain a 'scenarios' list.")
    return [scenario for scenario in scenarios if isinstance(scenario, dict)]


def build_pilot_readiness_report(
    *,
    semantic_session: dict[str, Any],
    baseline_session: dict[str, Any],
    scenario_pack: list[dict[str, Any]],
) -> dict[str, Any]:
    semantic_validation = validate_session_telemetry(semantic_session)
    baseline_validation = validate_session_telemetry(baseline_session)
    return {
        "schemaVersion": "1.0.0",
        "baselineFlows": [flow.to_dict() for flow in build_baseline_flow_catalog()],
        "telemetryValidation": {
            "semanticSession": semantic_validation.to_dict(),
            "baselineSession": baseline_validation.to_dict(),
            "conditionCoverage": compare_condition_event_coverage(semantic_session, baseline_session),
        },
        "pilotScenarioPack": {
            "scenarioCount": len(scenario_pack),
            "scenarios": scenario_pack,
        },
    }
