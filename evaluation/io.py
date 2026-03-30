from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class EvaluationIoError(RuntimeError):
    """Raised when an evaluation case or report cannot be loaded safely."""


@dataclass(frozen=True)
class EvaluationCase:
    fixture_id: str
    series_id: str
    segmentation_id: str
    series_length: int
    ground_truth: dict[str, Any]
    prediction: dict[str, Any]
    session_log: dict[str, Any] | None
    prototype_drift_values: tuple[float, ...]
    notes: str = ""


def load_evaluation_case(path: str | Path) -> EvaluationCase:
    fixture_path = Path(path)
    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvaluationIoError(f"Evaluation fixture was not found: {fixture_path}") from exc
    except json.JSONDecodeError as exc:
        raise EvaluationIoError(f"Evaluation fixture is not valid JSON: {fixture_path}") from exc

    if not isinstance(payload, dict):
        raise EvaluationIoError(f"Evaluation fixture must decode to an object: {fixture_path}")

    required_fields = ("fixtureId", "seriesId", "segmentationId", "seriesLength", "groundTruth", "prediction")
    for field_name in required_fields:
        if field_name not in payload:
            raise EvaluationIoError(f"Evaluation fixture is missing required field '{field_name}': {fixture_path}")

    ground_truth = payload["groundTruth"]
    prediction = payload["prediction"]
    if not isinstance(ground_truth, dict) or not isinstance(prediction, dict):
        raise EvaluationIoError(f"Evaluation fixture must include object-valued groundTruth and prediction: {fixture_path}")

    drift_values = payload.get("prototypeDriftValues", [])
    if not isinstance(drift_values, list):
        raise EvaluationIoError(f"Evaluation fixture field 'prototypeDriftValues' must be a list: {fixture_path}")

    session_log = payload.get("sessionLog")
    if session_log is not None and not isinstance(session_log, dict):
        raise EvaluationIoError(f"Evaluation fixture field 'sessionLog' must be an object when present: {fixture_path}")

    return EvaluationCase(
        fixture_id=str(payload["fixtureId"]),
        series_id=str(payload["seriesId"]),
        segmentation_id=str(payload["segmentationId"]),
        series_length=int(payload["seriesLength"]),
        ground_truth=ground_truth,
        prediction=prediction,
        session_log=session_log,
        prototype_drift_values=tuple(float(value) for value in drift_values),
        notes=str(payload.get("notes", "")),
    )


def write_evaluation_report(report: dict[str, Any], path: str | Path) -> Path:
    target_path = Path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return target_path
