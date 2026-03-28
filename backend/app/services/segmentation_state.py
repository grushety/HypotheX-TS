from typing import Any

from app.domain.state_models import (
    SegmentationHistoryEntry,
    SegmentationSnapshot,
    SegmentationState,
    SegmentationStateError,
    create_snapshot_from_payload,
    validate_snapshot_segments,
)


class SegmentationStateService:
    def create_state(self, payload: dict[str, Any]) -> SegmentationState:
        snapshot = create_snapshot_from_payload(payload, version=1)
        return SegmentationState(
            schemaVersion="1.0.0",
            stateId=f"state-{snapshot.segmentationId}",
            segmentationId=snapshot.segmentationId,
            seriesId=snapshot.seriesId,
            currentVersion=snapshot.version,
            currentSnapshot=snapshot,
            history=(),
        )

    def apply_update(
        self,
        state: SegmentationState,
        next_payload: dict[str, Any],
        *,
        action_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> SegmentationState:
        next_snapshot = create_snapshot_from_payload(
            next_payload,
            version=state.currentVersion + 1,
        )
        self._validate_transition(state.currentSnapshot, next_snapshot)

        history_entry = SegmentationHistoryEntry(
            entryId=f"{state.stateId}-history-{len(state.history) + 1}",
            sequence=len(state.history) + 1,
            actionType=action_type,
            beforeVersion=state.currentSnapshot.version,
            afterVersion=next_snapshot.version,
            beforeSnapshot=state.currentSnapshot,
            afterSnapshot=next_snapshot,
            metadata=dict(metadata or {}),
        )

        return SegmentationState(
            schemaVersion=state.schemaVersion,
            stateId=state.stateId,
            segmentationId=state.segmentationId,
            seriesId=state.seriesId,
            currentVersion=next_snapshot.version,
            currentSnapshot=next_snapshot,
            history=(*state.history, history_entry),
        )

    def _validate_transition(
        self,
        previous_snapshot: SegmentationSnapshot,
        next_snapshot: SegmentationSnapshot,
    ) -> None:
        if next_snapshot.segmentationId != previous_snapshot.segmentationId:
            raise SegmentationStateError("Segmentation updates must preserve segmentationId.")
        if next_snapshot.seriesId != previous_snapshot.seriesId:
            raise SegmentationStateError("Segmentation updates must preserve seriesId.")

        validate_snapshot_segments(next_snapshot.segments)

        if next_snapshot.segments[0].start_index != previous_snapshot.segments[0].start_index:
            raise SegmentationStateError("Segmentation updates must preserve the covered start index.")
        if next_snapshot.segments[-1].end_index != previous_snapshot.segments[-1].end_index:
            raise SegmentationStateError("Segmentation updates must preserve the covered end index.")
