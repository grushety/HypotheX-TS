import copy

import pytest

from app.domain.state_models import SegmentationStateError
from app.services.segmentation_state import SegmentationStateService


def create_segmentation_payload():
    return {
        "schemaVersion": "1.0.0",
        "segmentationId": "seg-001",
        "seriesId": "series-001",
        "segments": [
            {
                "segmentId": "segment-001",
                "startIndex": 0,
                "endIndex": 4,
                "label": "trend",
                "provenance": "user",
            },
            {
                "segmentId": "segment-002",
                "startIndex": 5,
                "endIndex": 9,
                "label": "plateau",
                "provenance": "user",
            },
        ],
    }


def test_create_state_builds_versioned_segmentation_source_of_truth():
    service = SegmentationStateService()

    state = service.create_state(create_segmentation_payload())

    assert state.stateId == "state-seg-001"
    assert state.currentVersion == 1
    assert state.currentSnapshot.segments[0].segment_id == "segment-001"
    assert state.history == ()


def test_apply_update_records_before_after_history_for_valid_edit():
    service = SegmentationStateService()
    state = service.create_state(create_segmentation_payload())
    next_payload = create_segmentation_payload()
    next_payload["segments"][0]["endIndex"] = 3
    next_payload["segments"][1]["startIndex"] = 4

    next_state = service.apply_update(
        state,
        next_payload,
        action_type="edit_boundary",
        metadata={"requestedBy": "user"},
    )

    assert next_state.currentVersion == 2
    assert next_state.currentSnapshot.segments[0].end_index == 3
    assert len(next_state.history) == 1
    assert next_state.history[0].beforeVersion == 1
    assert next_state.history[0].afterVersion == 2
    assert next_state.history[0].beforeSnapshot.segments[0].end_index == 4
    assert next_state.history[0].afterSnapshot.segments[0].end_index == 3
    assert state.currentSnapshot.segments[0].end_index == 4


def test_apply_update_rejects_overlapping_segments_without_mutating_state():
    service = SegmentationStateService()
    state = service.create_state(create_segmentation_payload())
    invalid_payload = copy.deepcopy(create_segmentation_payload())
    invalid_payload["segments"][0]["endIndex"] = 6
    invalid_payload["segments"][1]["startIndex"] = 5

    with pytest.raises(
        SegmentationStateError,
        match="contiguous and non-overlapping",
    ):
        service.apply_update(
            state,
            invalid_payload,
            action_type="edit_boundary",
            metadata={"requestedBy": "user"},
        )

    assert state.currentVersion == 1
    assert state.currentSnapshot.segments[0].end_index == 4
    assert state.history == ()
