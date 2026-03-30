import json
import importlib
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

evaluate_fixture_case = importlib.import_module("evaluation.harness").evaluate_fixture_case
evaluation_io = importlib.import_module("evaluation.io")
load_evaluation_case = evaluation_io.load_evaluation_case
write_evaluation_report = evaluation_io.write_evaluation_report


FIXTURES_DIR = ROOT_DIR / "evaluation" / "fixtures"


def test_evaluation_harness_scores_known_good_fixture():
    report = evaluate_fixture_case(FIXTURES_DIR / "known-good.json")
    payload = report.to_dict()

    assert payload["metrics"]["segmentationQuality"]["macroIoU"] == 1.0
    assert payload["metrics"]["segmentationQuality"]["boundaryF1"]["f1"] == 1.0
    assert payload["metrics"]["segmentationQuality"]["covering"] == 1.0
    assert payload["metrics"]["stability"]["overSegmentationRate"] == 0.0
    assert payload["metrics"]["constraintAwareness"]["violationRate"] == 0.0


def test_evaluation_harness_scores_known_bad_fixture():
    report = evaluate_fixture_case(FIXTURES_DIR / "known-bad.json")
    payload = report.to_dict()

    assert payload["metrics"]["segmentationQuality"]["macroIoU"] < 1.0
    assert payload["metrics"]["segmentationQuality"]["boundaryF1"]["f1"] < 1.0
    assert payload["metrics"]["segmentationQuality"]["covering"] < 1.0
    assert payload["metrics"]["stability"]["overSegmentationRate"] == 1.0
    assert payload["metrics"]["stability"]["prototypeDrift"]["max"] == 0.52
    assert payload["metrics"]["constraintAwareness"]["violationRate"] == 1.0


def test_evaluation_report_can_be_written_as_machine_readable_json(tmp_path):
    case = load_evaluation_case(FIXTURES_DIR / "known-good.json")
    report = evaluate_fixture_case(FIXTURES_DIR / "known-good.json").to_dict()
    output_path = write_evaluation_report(report, tmp_path / f"{case.fixture_id}-report.json")

    written_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert written_payload["fixtureId"] == "known-good-001"
    assert written_payload["unsupportedMetrics"]["wari"].startswith("Not implemented")
