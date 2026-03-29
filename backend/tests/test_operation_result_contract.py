import json
from pathlib import Path

from app.services.operations.structural import StructuralOperationsService
from app.services.operations.value_ops import ValueOperationsService
from app.services.segmentation_state import SegmentationStateService


def create_segmentation_payload():
    return {
        "schemaVersion": "1.0.0",
        "segmentationId": "seg-contract-001",
        "seriesId": "series-contract-001",
        "segments": [
            {
                "segmentId": "segment-trend",
                "startIndex": 0,
                "endIndex": 3,
                "label": "trend",
                "provenance": "user",
            },
            {
                "segmentId": "segment-plateau",
                "startIndex": 4,
                "endIndex": 7,
                "label": "plateau",
                "provenance": "user",
            },
        ],
    }


def create_series():
    return [0.0, 0.2, 0.4, 0.6, 1.0, 1.0, 1.01, 0.99]


def test_operation_result_contract_covers_pass_warn_and_fail_states():
    state = SegmentationStateService().create_state(create_segmentation_payload())

    pass_result = ValueOperationsService().apply_operation(
        state,
        create_series(),
        segment_id="segment-plateau",
        operation_type="shift_level",
        parameters={"delta": 0.2},
    )
    warn_result = StructuralOperationsService().reclassify_segment(
        state,
        create_series(),
        segment_id="segment-plateau",
        new_label="trend",
    )
    fail_result = StructuralOperationsService().edit_boundary(
        state,
        create_series(),
        left_segment_id="segment-trend",
        right_segment_id="segment-plateau",
        new_left_end_index=0,
    )

    assert pass_result.status == "PASS"
    assert pass_result.applied is True
    assert pass_result.to_dict()["violations"] == []

    warn_payload = warn_result.to_dict()
    assert warn_result.status == "WARN"
    assert warn_result.applied is True
    assert warn_payload["constraintMode"] == "soft"
    assert warn_payload["violations"][0]["constraintId"] == "monotonic_trend_consistency"

    fail_payload = fail_result.to_dict()
    assert fail_result.status == "FAIL"
    assert fail_result.applied is False
    assert fail_payload["reasonCode"] == "CONSTRAINT_FAIL"
    assert fail_payload["violations"][0]["constraintId"] == "minimum_segment_duration"


def test_operation_result_fixture_is_valid_json_and_uses_shared_fields():
    fixture_path = Path("schemas/fixtures/operation-result.sample.json")
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert payload["schemaVersion"] == "1.0.0"
    assert payload["status"] in {"PASS", "WARN", "FAIL"}
    assert isinstance(payload["applied"], bool)
    assert "violations" in payload
    assert "state" in payload
    assert "legalityChecks" in payload
