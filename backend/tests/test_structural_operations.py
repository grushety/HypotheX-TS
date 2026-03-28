from app.services.operations.structural import StructuralOperationError, StructuralOperationsService
from app.services.segmentation_state import SegmentationStateService


def create_segmentation_payload():
    return {
        "schemaVersion": "1.0.0",
        "segmentationId": "seg-ops-001",
        "seriesId": "series-ops-001",
        "segments": [
            {
                "segmentId": "segment-001",
                "startIndex": 0,
                "endIndex": 3,
                "label": "trend",
                "provenance": "user",
            },
            {
                "segmentId": "segment-002",
                "startIndex": 4,
                "endIndex": 7,
                "label": "plateau",
                "provenance": "user",
            },
            {
                "segmentId": "segment-003",
                "startIndex": 8,
                "endIndex": 11,
                "label": "plateau",
                "provenance": "user",
            },
        ],
    }


def create_series():
    return [0.0, 0.2, 0.4, 0.6, 1.0, 1.0, 1.01, 0.99, 1.0, 1.0, 1.0, 1.0]


def test_edit_boundary_updates_only_adjacent_segments_and_records_history():
    state = SegmentationStateService().create_state(create_segmentation_payload())
    service = StructuralOperationsService()

    result = service.edit_boundary(
        state,
        create_series(),
        left_segment_id="segment-001",
        right_segment_id="segment-002",
        new_left_end_index=2,
    )

    assert result.status == "APPLIED"
    assert result.state.currentVersion == 2
    assert result.state.currentSnapshot.segments[0].end_index == 2
    assert result.state.currentSnapshot.segments[1].start_index == 3
    assert result.state.currentSnapshot.segments[2].start_index == 8
    assert result.constraintEvaluation is not None
    assert result.state.history[-1].actionType == "edit_boundary"


def test_split_creates_two_contiguous_children_with_valid_boundaries():
    state = SegmentationStateService().create_state(create_segmentation_payload())
    service = StructuralOperationsService()

    result = service.split_segment(
        state,
        create_series(),
        segment_id="segment-001",
        split_after_index=1,
    )

    assert result.status == "APPLIED"
    child_segments = result.state.currentSnapshot.segments[:2]
    assert [segment.segment_id for segment in child_segments] == ["segment-001-a", "segment-001-b"]
    assert child_segments[0].start_index == 0
    assert child_segments[0].end_index == 1
    assert child_segments[1].start_index == 2
    assert child_segments[1].end_index == 3


def test_merge_combines_adjacent_compatible_segments_and_preserves_coverage():
    state = SegmentationStateService().create_state(create_segmentation_payload())
    service = StructuralOperationsService()

    result = service.merge_segments(
        state,
        create_series(),
        left_segment_id="segment-002",
        right_segment_id="segment-003",
    )

    assert result.status == "APPLIED"
    merged_segment = result.state.currentSnapshot.segments[1]
    assert len(result.state.currentSnapshot.segments) == 2
    assert merged_segment.segment_id == "segment-002"
    assert merged_segment.start_index == 4
    assert merged_segment.end_index == 11
    assert merged_segment.label == "plateau"


def test_reclassify_changes_only_label_and_preserves_boundaries():
    state = SegmentationStateService().create_state(create_segmentation_payload())
    service = StructuralOperationsService()

    result = service.reclassify_segment(
        state,
        create_series(),
        segment_id="segment-002",
        new_label="event",
    )

    assert result.status == "APPLIED"
    reclassified = result.state.currentSnapshot.segments[1]
    assert reclassified.label == "event"
    assert reclassified.start_index == 4
    assert reclassified.end_index == 7
    assert result.state.history[-1].actionType == "reclassify"


def test_invalid_structural_operations_return_explicit_feedback_without_mutating_state():
    state = SegmentationStateService().create_state(create_segmentation_payload())
    service = StructuralOperationsService()

    denied_merge = service.merge_segments(
        state,
        create_series(),
        left_segment_id="segment-001",
        right_segment_id="segment-002",
    )
    denied_boundary = service.edit_boundary(
        state,
        create_series(),
        left_segment_id="segment-001",
        right_segment_id="segment-002",
        new_left_end_index=0,
    )

    assert denied_merge.status == "DENY"
    assert denied_merge.reasonCode == "INCOMPATIBLE_SEGMENTS"
    assert denied_boundary.status == "DENY"
    assert denied_boundary.reasonCode == "CONSTRAINT_FAIL"
    assert denied_merge.state.currentVersion == 1
    assert denied_boundary.state.currentVersion == 1
    assert state.history == ()


def test_invalid_segment_lookup_fails_explicitly():
    state = SegmentationStateService().create_state(create_segmentation_payload())
    service = StructuralOperationsService()

    try:
        service.reclassify_segment(
            state,
            create_series(),
            segment_id="missing-segment",
            new_label="event",
        )
    except StructuralOperationError as exc:
        assert "missing-segment" in str(exc)
    else:
        raise AssertionError("Expected StructuralOperationError for missing segment lookup.")
