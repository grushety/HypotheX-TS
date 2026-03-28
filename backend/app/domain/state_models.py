from dataclasses import dataclass
from typing import Any


class SegmentationStateError(RuntimeError):
    """Raised when segmentation state cannot be created or updated safely."""


@dataclass(frozen=True)
class StateSegment:
    segment_id: str
    start_index: int
    end_index: int
    label: str
    provenance: str
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "segmentId": self.segment_id,
            "startIndex": self.start_index,
            "endIndex": self.end_index,
            "label": self.label,
            "provenance": self.provenance,
        }
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        return payload


@dataclass(frozen=True)
class SegmentationSnapshot:
    schemaVersion: str
    segmentationId: str
    seriesId: str
    version: int
    segments: tuple[StateSegment, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schemaVersion,
            "segmentationId": self.segmentationId,
            "seriesId": self.seriesId,
            "version": self.version,
            "segments": [segment.to_dict() for segment in self.segments],
        }


@dataclass(frozen=True)
class SegmentationHistoryEntry:
    entryId: str
    sequence: int
    actionType: str
    beforeVersion: int
    afterVersion: int
    beforeSnapshot: SegmentationSnapshot
    afterSnapshot: SegmentationSnapshot
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "entryId": self.entryId,
            "sequence": self.sequence,
            "actionType": self.actionType,
            "beforeVersion": self.beforeVersion,
            "afterVersion": self.afterVersion,
            "beforeSnapshot": self.beforeSnapshot.to_dict(),
            "afterSnapshot": self.afterSnapshot.to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SegmentationState:
    schemaVersion: str
    stateId: str
    segmentationId: str
    seriesId: str
    currentVersion: int
    currentSnapshot: SegmentationSnapshot
    history: tuple[SegmentationHistoryEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schemaVersion,
            "stateId": self.stateId,
            "segmentationId": self.segmentationId,
            "seriesId": self.seriesId,
            "currentVersion": self.currentVersion,
            "currentSnapshot": self.currentSnapshot.to_dict(),
            "history": [entry.to_dict() for entry in self.history],
        }


def create_snapshot_from_payload(payload: dict[str, Any], *, version: int = 1) -> SegmentationSnapshot:
    segmentation_id = str(payload.get("segmentationId", ""))
    series_id = str(payload.get("seriesId", ""))
    schema_version = str(payload.get("schemaVersion", "1.0.0"))
    segments_payload = payload.get("segments")

    if not segmentation_id or not series_id:
        raise SegmentationStateError("Segmentation payload must include non-empty segmentationId and seriesId.")
    if not isinstance(segments_payload, list) or not segments_payload:
        raise SegmentationStateError("Segmentation payload must include a non-empty segments list.")

    segments = tuple(_coerce_segment(segment_payload) for segment_payload in segments_payload)
    validate_snapshot_segments(segments)

    return SegmentationSnapshot(
        schemaVersion=schema_version,
        segmentationId=segmentation_id,
        seriesId=series_id,
        version=version,
        segments=segments,
    )


def validate_snapshot_segments(segments: tuple[StateSegment, ...]) -> None:
    if not segments:
        raise SegmentationStateError("Segmentation state requires at least one segment.")

    previous_end: int | None = None
    for index, segment in enumerate(segments):
        if segment.start_index < 0 or segment.end_index < 0:
            raise SegmentationStateError("Segment indices must be non-negative.")
        if segment.end_index < segment.start_index:
            raise SegmentationStateError(
                f"Segment '{segment.segment_id}' has endIndex before startIndex."
            )
        if index == 0:
            previous_end = segment.end_index
            continue

        assert previous_end is not None
        if segment.start_index != previous_end + 1:
            raise SegmentationStateError(
                "Segmentation state must remain contiguous and non-overlapping between adjacent segments."
            )
        previous_end = segment.end_index


def _coerce_segment(payload: dict[str, Any]) -> StateSegment:
    segment_id = str(payload.get("segmentId", ""))
    label = str(payload.get("label", ""))
    provenance = str(payload.get("provenance", ""))
    if not segment_id or not label or not provenance:
        raise SegmentationStateError(
            "Each segment must include non-empty segmentId, label, and provenance values."
        )

    confidence = payload.get("confidence")
    return StateSegment(
        segment_id=segment_id,
        start_index=int(payload["startIndex"]),
        end_index=int(payload["endIndex"]),
        label=label,
        provenance=provenance,
        confidence=float(confidence) if confidence is not None else None,
    )
