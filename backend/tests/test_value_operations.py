import pytest
import numpy as np

from app.services.operations.value_ops import ValueOperationError, ValueOperationsService
from app.services.segmentation_state import SegmentationStateService


def create_segmentation_payload():
    return {
        "schemaVersion": "1.0.0",
        "segmentationId": "seg-value-001",
        "seriesId": "series-value-001",
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
            {
                "segmentId": "segment-spike",
                "startIndex": 8,
                "endIndex": 10,
                "label": "spike",
                "provenance": "user",
            },
            {
                "segmentId": "segment-event",
                "startIndex": 11,
                "endIndex": 14,
                "label": "event",
                "provenance": "user",
            },
        ],
    }


def create_series():
    return np.asarray(
        [0.0, 0.2, 0.4, 0.6, 1.0, 1.0, 1.01, 0.99, 0.0, 5.0, 0.0, 2.0, 3.0, 4.0, 5.0, 9.0],
        dtype=np.float64,
    )


def test_shift_level_applies_to_plateau_and_keeps_constraint_feedback():
    state = SegmentationStateService().create_state(create_segmentation_payload())
    service = ValueOperationsService()

    result = service.apply_operation(
        state,
        create_series(),
        segment_id="segment-plateau",
        operation_type="shift_level",
        parameters={"delta": 0.25},
    )

    assert result.status == "APPLIED"
    assert result.editedSeries[4:8].tolist() == [1.25, 1.25, 1.26, 1.24]
    assert result.editedSeries[:4].tolist() == [0.0, 0.2, 0.4, 0.6]
    assert result.constraintEvaluation is not None
    assert result.constraintEvaluation.status in {"PASS", "WARN"}
    assert result.state.currentVersion == 1


def test_change_slope_applies_only_to_trend_segment():
    state = SegmentationStateService().create_state(create_segmentation_payload())
    service = ValueOperationsService()

    result = service.apply_operation(
        state,
        create_series(),
        segment_id="segment-trend",
        operation_type="change_slope",
        parameters={"slopeDelta": 0.1},
    )

    assert result.status == "APPLIED"
    assert result.editedSeries[:4].tolist() == pytest.approx([-0.15, 0.15, 0.45, 0.75])
    assert result.editedSeries[4:].tolist() == create_series()[4:].tolist()


def test_spike_operations_cover_scale_and_suppress_edge_cases():
    state = SegmentationStateService().create_state(create_segmentation_payload())
    service = ValueOperationsService()

    scaled = service.apply_operation(
        state,
        create_series(),
        segment_id="segment-spike",
        operation_type="scale_spike",
        parameters={"scaleFactor": 0.5},
    )
    suppressed = service.apply_operation(
        state,
        create_series(),
        segment_id="segment-spike",
        operation_type="suppress_spike",
    )

    assert scaled.status == "APPLIED"
    assert scaled.editedSeries[8:11].tolist() == pytest.approx(
        [0.8333333333333333, 3.333333333333333, 0.8333333333333333]
    )
    assert suppressed.status == "APPLIED"
    assert suppressed.editedSeries[8:11].tolist() == pytest.approx(
        [1.6666666666666665, 1.6666666666666665, 1.6666666666666665]
    )


def test_event_operations_cover_shift_and_remove_without_touching_other_regions():
    state = SegmentationStateService().create_state(create_segmentation_payload())
    service = ValueOperationsService()

    shifted = service.apply_operation(
        state,
        create_series(),
        segment_id="segment-event",
        operation_type="shift_event",
        parameters={"offset": 1},
    )
    removed = service.apply_operation(
        state,
        create_series(),
        segment_id="segment-event",
        operation_type="remove_event",
    )

    assert shifted.status == "APPLIED"
    assert shifted.editedSeries[:11].tolist() == create_series()[:11].tolist()
    assert shifted.editedSeries[11:15].tolist() == [2.0, 2.0, 3.0, 4.0]
    assert removed.status == "APPLIED"
    assert removed.editedSeries[11:15].tolist() == pytest.approx([1.8, 3.6, 5.4, 7.2])
    assert removed.editedSeries[15] == 9.0


def test_illegal_chunk_type_combination_is_rejected_before_mutation():
    state = SegmentationStateService().create_state(create_segmentation_payload())
    service = ValueOperationsService()
    original = create_series()

    result = service.apply_operation(
        state,
        original,
        segment_id="segment-plateau",
        operation_type="suppress_spike",
    )

    assert result.status == "DENY"
    assert result.reasonCode == "OPERATION_NOT_ALLOWED"
    assert result.editedSeries.tolist() == original.tolist()


def test_invalid_parameters_and_unknown_segment_fail_explicitly():
    state = SegmentationStateService().create_state(create_segmentation_payload())
    service = ValueOperationsService()

    denied = service.apply_operation(
        state,
        create_series(),
        segment_id="segment-event",
        operation_type="shift_event",
        parameters={"offset": 0},
    )

    assert denied.status == "DENY"
    assert denied.reasonCode == "INVALID_PARAMETERS"

    try:
        service.apply_operation(
            state,
            create_series(),
            segment_id="missing-segment",
            operation_type="shift_level",
            parameters={"delta": 1.0},
        )
    except ValueOperationError as exc:
        assert "missing-segment" in str(exc)
    else:
        raise AssertionError("Expected ValueOperationError for missing segment lookup.")
