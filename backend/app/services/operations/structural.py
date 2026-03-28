from dataclasses import dataclass
from typing import Any

from app.core.domain_config import DomainConfig, load_domain_config
from app.domain.state_models import SegmentationState, StateSegment
from app.domain.validation import OperationLegalityResult, validate_operation_legality
from app.services.constraint_engine import ConstraintEngine, ConstraintEvaluationResult
from app.services.segmentation_state import SegmentationStateService


class StructuralOperationError(RuntimeError):
    """Raised when a structural operation request is malformed."""


@dataclass(frozen=True)
class StructuralOperationResult:
    schemaVersion: str
    operationType: str
    status: str
    reasonCode: str
    message: str
    state: SegmentationState
    constraintEvaluation: ConstraintEvaluationResult | None
    legalityChecks: tuple[OperationLegalityResult, ...]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schemaVersion": self.schemaVersion,
            "operationType": self.operationType,
            "status": self.status,
            "reasonCode": self.reasonCode,
            "message": self.message,
            "state": self.state.to_dict(),
            "legalityChecks": [entry.to_dict() for entry in self.legalityChecks],
            "metadata": dict(self.metadata),
        }
        if self.constraintEvaluation is not None:
            payload["constraintEvaluation"] = self.constraintEvaluation.to_dict()
        return payload


class StructuralOperationsService:
    def __init__(
        self,
        *,
        state_service: SegmentationStateService | None = None,
        constraint_engine: ConstraintEngine | None = None,
        domain_config: DomainConfig | None = None,
    ):
        self._state_service = state_service or SegmentationStateService()
        self._domain_config = domain_config or load_domain_config()
        self._constraint_engine = constraint_engine or ConstraintEngine(domain_config=self._domain_config)

    def edit_boundary(
        self,
        state: SegmentationState,
        series: Any,
        *,
        left_segment_id: str,
        right_segment_id: str,
        new_left_end_index: int,
        constraint_mode: str | None = None,
    ) -> StructuralOperationResult:
        left_index = self._find_segment_index(state, left_segment_id)
        right_index = self._find_segment_index(state, right_segment_id)
        if right_index != left_index + 1:
            return self._deny(
                "edit_boundary",
                "NON_ADJACENT_SEGMENTS",
                "Boundary edits require two adjacent segments in the current segmentation.",
                state,
                metadata={
                    "leftSegmentId": left_segment_id,
                    "rightSegmentId": right_segment_id,
                    "newLeftEndIndex": new_left_end_index,
                },
            )

        segments = list(state.currentSnapshot.segments)
        left_segment = segments[left_index]
        right_segment = segments[right_index]
        previous_boundary = left_segment.end_index
        if new_left_end_index == previous_boundary:
            return self._deny(
                "edit_boundary",
                "NO_OP",
                "Boundary edit request does not change the shared boundary.",
                state,
                metadata={
                    "leftSegmentId": left_segment_id,
                    "rightSegmentId": right_segment_id,
                    "previousBoundary": previous_boundary,
                    "newBoundary": new_left_end_index,
                },
            )

        left_legality = self._validate_boundary_legality(left_segment, new_left_end_index - previous_boundary)
        right_legality = self._validate_boundary_legality(right_segment, previous_boundary - new_left_end_index)
        legality_checks = (left_legality, right_legality)
        denied_legality = next((entry for entry in legality_checks if entry.status == "DENY"), None)
        if denied_legality is not None:
            return self._deny(
                "edit_boundary",
                denied_legality.reasonCode,
                denied_legality.message,
                state,
                legality_checks=legality_checks,
                metadata={
                    "leftSegmentId": left_segment_id,
                    "rightSegmentId": right_segment_id,
                    "previousBoundary": previous_boundary,
                    "newBoundary": new_left_end_index,
                },
            )

        segments[left_index] = self._replace_segment(left_segment, end_index=new_left_end_index)
        segments[right_index] = self._replace_segment(right_segment, start_index=new_left_end_index + 1)
        return self._apply_candidate(
            operation_type="edit_boundary",
            state=state,
            series=series,
            candidate_segments=tuple(segments),
            constraint_mode=constraint_mode,
            legality_checks=legality_checks,
            metadata={
                "leftSegmentId": left_segment_id,
                "rightSegmentId": right_segment_id,
                "previousBoundary": previous_boundary,
                "newBoundary": new_left_end_index,
            },
        )

    def split_segment(
        self,
        state: SegmentationState,
        series: Any,
        *,
        segment_id: str,
        split_after_index: int,
        constraint_mode: str | None = None,
    ) -> StructuralOperationResult:
        segment_index = self._find_segment_index(state, segment_id)
        segment = state.currentSnapshot.segments[segment_index]
        legality = validate_operation_legality(segment.label, "split", domain_config=self._domain_config)
        if legality.status == "DENY":
            return self._deny(
                "split",
                legality.reasonCode,
                legality.message,
                state,
                legality_checks=(legality,),
                metadata={"segmentId": segment_id, "splitAfterIndex": split_after_index},
            )
        if not (segment.start_index <= split_after_index < segment.end_index):
            return self._deny(
                "split",
                "INVALID_SPLIT_POINT",
                "Split point must fall strictly inside the target segment.",
                state,
                legality_checks=(legality,),
                metadata={"segmentId": segment_id, "splitAfterIndex": split_after_index},
            )

        left_child_id = f"{segment.segment_id}-a"
        right_child_id = f"{segment.segment_id}-b"
        replacement_segments = [
            StateSegment(
                segment_id=left_child_id,
                start_index=segment.start_index,
                end_index=split_after_index,
                label=segment.label,
                provenance=segment.provenance,
                confidence=segment.confidence,
            ),
            StateSegment(
                segment_id=right_child_id,
                start_index=split_after_index + 1,
                end_index=segment.end_index,
                label=segment.label,
                provenance=segment.provenance,
                confidence=segment.confidence,
            ),
        ]

        candidate_segments = list(state.currentSnapshot.segments)
        candidate_segments[segment_index : segment_index + 1] = replacement_segments
        return self._apply_candidate(
            operation_type="split",
            state=state,
            series=series,
            candidate_segments=tuple(candidate_segments),
            constraint_mode=constraint_mode,
            legality_checks=(legality,),
            metadata={
                "segmentId": segment_id,
                "splitAfterIndex": split_after_index,
                "childSegmentIds": [left_child_id, right_child_id],
            },
        )

    def merge_segments(
        self,
        state: SegmentationState,
        series: Any,
        *,
        left_segment_id: str,
        right_segment_id: str,
        constraint_mode: str | None = None,
    ) -> StructuralOperationResult:
        left_index = self._find_segment_index(state, left_segment_id)
        right_index = self._find_segment_index(state, right_segment_id)
        if right_index != left_index + 1:
            return self._deny(
                "merge",
                "NON_ADJACENT_SEGMENTS",
                "Merge requires two adjacent segments in the current segmentation.",
                state,
                metadata={"leftSegmentId": left_segment_id, "rightSegmentId": right_segment_id},
            )

        segments = list(state.currentSnapshot.segments)
        left_segment = segments[left_index]
        right_segment = segments[right_index]
        if left_segment.label != right_segment.label:
            return self._deny(
                "merge",
                "INCOMPATIBLE_SEGMENTS",
                "Merge requires adjacent segments with the same semantic label.",
                state,
                metadata={
                    "leftSegmentId": left_segment_id,
                    "rightSegmentId": right_segment_id,
                    "leftLabel": left_segment.label,
                    "rightLabel": right_segment.label,
                },
            )

        left_legality = validate_operation_legality(left_segment.label, "merge", domain_config=self._domain_config)
        right_legality = validate_operation_legality(right_segment.label, "merge", domain_config=self._domain_config)
        legality_checks = (left_legality, right_legality)
        denied_legality = next((entry for entry in legality_checks if entry.status == "DENY"), None)
        if denied_legality is not None:
            return self._deny(
                "merge",
                denied_legality.reasonCode,
                denied_legality.message,
                state,
                legality_checks=legality_checks,
                metadata={"leftSegmentId": left_segment_id, "rightSegmentId": right_segment_id},
            )

        merged_segment = StateSegment(
            segment_id=left_segment.segment_id,
            start_index=left_segment.start_index,
            end_index=right_segment.end_index,
            label=left_segment.label,
            provenance=left_segment.provenance,
            confidence=self._merge_confidence(left_segment, right_segment),
        )
        segments[left_index : right_index + 1] = [merged_segment]
        return self._apply_candidate(
            operation_type="merge",
            state=state,
            series=series,
            candidate_segments=tuple(segments),
            constraint_mode=constraint_mode,
            legality_checks=legality_checks,
            metadata={
                "leftSegmentId": left_segment_id,
                "rightSegmentId": right_segment_id,
                "mergedSegmentId": merged_segment.segment_id,
            },
        )

    def reclassify_segment(
        self,
        state: SegmentationState,
        series: Any,
        *,
        segment_id: str,
        new_label: str,
        constraint_mode: str | None = None,
    ) -> StructuralOperationResult:
        segment_index = self._find_segment_index(state, segment_id)
        segment = state.currentSnapshot.segments[segment_index]
        if new_label not in self._domain_config.active_chunk_types:
            return self._deny(
                "reclassify",
                "UNKNOWN_TARGET_LABEL",
                f"Target label '{new_label}' is not active in the current ontology.",
                state,
                metadata={"segmentId": segment_id, "previousLabel": segment.label, "newLabel": new_label},
            )
        if new_label == segment.label:
            return self._deny(
                "reclassify",
                "NO_OP",
                "Reclassify request does not change the segment label.",
                state,
                metadata={"segmentId": segment_id, "previousLabel": segment.label, "newLabel": new_label},
            )

        segments = list(state.currentSnapshot.segments)
        segments[segment_index] = self._replace_segment(segment, label=new_label)
        return self._apply_candidate(
            operation_type="reclassify",
            state=state,
            series=series,
            candidate_segments=tuple(segments),
            constraint_mode=constraint_mode,
            legality_checks=(),
            metadata={"segmentId": segment_id, "previousLabel": segment.label, "newLabel": new_label},
        )

    def _apply_candidate(
        self,
        *,
        operation_type: str,
        state: SegmentationState,
        series: Any,
        candidate_segments: tuple[StateSegment, ...],
        constraint_mode: str | None,
        legality_checks: tuple[OperationLegalityResult, ...],
        metadata: dict[str, Any],
    ) -> StructuralOperationResult:
        constraint_evaluation = self._constraint_engine.evaluate(
            series,
            [segment.to_dict() for segment in candidate_segments],
            operation_id=f"{state.stateId}-{operation_type}-{state.currentVersion + 1}",
            constraint_mode=constraint_mode,
        )
        if constraint_evaluation.status == "FAIL":
            return self._deny(
                operation_type,
                "CONSTRAINT_FAIL",
                "Structural operation violated one or more hard constraints.",
                state,
                constraint_evaluation=constraint_evaluation,
                legality_checks=legality_checks,
                metadata=metadata,
            )

        next_state = self._state_service.apply_update(
            state,
            self._build_snapshot_payload(state, candidate_segments),
            action_type=operation_type,
            metadata={
                **metadata,
                "constraintStatus": constraint_evaluation.status,
                "constraintMode": constraint_evaluation.constraintMode,
                "violationCount": len(constraint_evaluation.violations),
            },
        )
        return StructuralOperationResult(
            schemaVersion="1.0.0",
            operationType=operation_type,
            status="APPLIED",
            reasonCode=constraint_evaluation.status,
            message=f"Structural operation '{operation_type}' applied successfully.",
            state=next_state,
            constraintEvaluation=constraint_evaluation,
            legalityChecks=legality_checks,
            metadata=metadata,
        )

    def _deny(
        self,
        operation_type: str,
        reason_code: str,
        message: str,
        state: SegmentationState,
        *,
        constraint_evaluation: ConstraintEvaluationResult | None = None,
        legality_checks: tuple[OperationLegalityResult, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> StructuralOperationResult:
        return StructuralOperationResult(
            schemaVersion="1.0.0",
            operationType=operation_type,
            status="DENY",
            reasonCode=reason_code,
            message=message,
            state=state,
            constraintEvaluation=constraint_evaluation,
            legalityChecks=legality_checks,
            metadata=dict(metadata or {}),
        )

    def _find_segment_index(self, state: SegmentationState, segment_id: str) -> int:
        for index, segment in enumerate(state.currentSnapshot.segments):
            if segment.segment_id == segment_id:
                return index
        raise StructuralOperationError(f"Segment '{segment_id}' is not present in the current segmentation state.")

    def _validate_boundary_legality(self, segment: StateSegment, delta: int) -> OperationLegalityResult:
        if delta == 0:
            return OperationLegalityResult(
                schemaVersion="1.0.0",
                ontologyName=self._domain_config.ontology_name,
                chunkType=segment.label,
                requestedOperation="edit_boundary",
                status="ALLOW",
                reasonCode="LEGAL",
                message=f"Boundary edit is legal for chunk type '{segment.label}'.",
                validOperations=(),
            )

        for requested_operation in self._boundary_operation_candidates(segment.label, delta):
            result = validate_operation_legality(
                segment.label,
                requested_operation,
                domain_config=self._domain_config,
            )
            if result.status == "ALLOW":
                return result

        denied = validate_operation_legality(
            segment.label,
            self._boundary_operation_candidates(segment.label, delta)[0],
            domain_config=self._domain_config,
        )
        return OperationLegalityResult(
            schemaVersion=denied.schemaVersion,
            ontologyName=denied.ontologyName,
            chunkType=denied.chunkType,
            requestedOperation="edit_boundary",
            status="DENY",
            reasonCode=denied.reasonCode,
            message=f"Boundary edit is not legal for chunk type '{segment.label}'.",
            validOperations=denied.validOperations,
        )

    def _boundary_operation_candidates(self, label: str, delta: int) -> tuple[str, ...]:
        if label == "trend":
            return ("extend",) if delta > 0 else ("shorten",)
        if label == "plateau":
            return ("extend",) if delta > 0 else ("shorten",)
        if label == "event":
            return ("change_duration",)
        if label == "spike":
            return ("widen",) if delta > 0 else ("narrow",)
        if label == "transition":
            return ("shift_onset",)
        if label == "periodic":
            return ("split",)
        return ("edit_boundary",)

    def _build_snapshot_payload(
        self,
        state: SegmentationState,
        segments: tuple[StateSegment, ...],
    ) -> dict[str, Any]:
        return {
            "schemaVersion": state.schemaVersion,
            "segmentationId": state.segmentationId,
            "seriesId": state.seriesId,
            "segments": [segment.to_dict() for segment in segments],
        }

    def _replace_segment(
        self,
        segment: StateSegment,
        *,
        start_index: int | None = None,
        end_index: int | None = None,
        label: str | None = None,
    ) -> StateSegment:
        return StateSegment(
            segment_id=segment.segment_id,
            start_index=segment.start_index if start_index is None else start_index,
            end_index=segment.end_index if end_index is None else end_index,
            label=segment.label if label is None else label,
            provenance=segment.provenance,
            confidence=segment.confidence,
        )

    def _merge_confidence(self, left_segment: StateSegment, right_segment: StateSegment) -> float | None:
        if left_segment.confidence is None and right_segment.confidence is None:
            return None
        values = [value for value in (left_segment.confidence, right_segment.confidence) if value is not None]
        return float(sum(values) / len(values))
