from dataclasses import dataclass
from typing import Any

from app.core.domain_config import DomainConfig, load_domain_config
from app.domain.signal_transforms import (
    SignalTransformError,
    change_slope,
    remove_event,
    scale_spike,
    shift_event,
    shift_level,
    suppress_spike,
)
from app.domain.state_models import SegmentationState
from app.domain.validation import OperationLegalityResult, validate_operation_legality
from app.services.constraint_engine import ConstraintEngine, ConstraintEvaluationResult


class ValueOperationError(RuntimeError):
    """Raised when a value operation request is malformed."""


@dataclass(frozen=True)
class ValueOperationResult:
    schemaVersion: str
    operationType: str
    status: str
    reasonCode: str
    message: str
    editedSeries: Any
    state: SegmentationState
    constraintEvaluation: ConstraintEvaluationResult | None
    legalityCheck: OperationLegalityResult | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schemaVersion": self.schemaVersion,
            "operationType": self.operationType,
            "status": self.status,
            "reasonCode": self.reasonCode,
            "message": self.message,
            "editedSeries": self._serialize_series(self.editedSeries),
            "state": self.state.to_dict(),
            "metadata": dict(self.metadata),
        }
        if self.constraintEvaluation is not None:
            payload["constraintEvaluation"] = self.constraintEvaluation.to_dict()
        if self.legalityCheck is not None:
            payload["legalityCheck"] = self.legalityCheck.to_dict()
        return payload

    def _serialize_series(self, series: Any) -> Any:
        return series.tolist() if hasattr(series, "tolist") else series


class ValueOperationsService:
    _OPERATIONS = {
        "shift_level": ("plateau", "shift_level"),
        "change_slope": ("trend", "change_slope"),
        "scale_spike": ("spike", "scale"),
        "suppress_spike": ("spike", "suppress"),
        "shift_event": ("event", "shift_in_time"),
        "remove_event": ("event", "remove"),
    }

    def __init__(
        self,
        *,
        constraint_engine: ConstraintEngine | None = None,
        domain_config: DomainConfig | None = None,
    ):
        self._domain_config = domain_config or load_domain_config()
        self._constraint_engine = constraint_engine or ConstraintEngine(domain_config=self._domain_config)

    def apply_operation(
        self,
        state: SegmentationState,
        series: Any,
        *,
        segment_id: str,
        operation_type: str,
        parameters: dict[str, Any] | None = None,
        constraint_mode: str | None = None,
    ) -> ValueOperationResult:
        normalized_operation = str(operation_type)
        if normalized_operation not in self._OPERATIONS:
            raise ValueOperationError(f"Unsupported value operation '{operation_type}'.")

        segment = self._find_segment(state, segment_id)
        required_label, legal_operation_name = self._OPERATIONS[normalized_operation]
        legality = validate_operation_legality(
            segment.label,
            legal_operation_name,
            domain_config=self._domain_config,
        )
        if legality.status == "DENY" or segment.label != required_label:
            return self._deny(
                operation_type=normalized_operation,
                reason_code="OPERATION_NOT_ALLOWED",
                message=(
                    f"Operation '{normalized_operation}' is only supported for chunk type "
                    f"'{required_label}', but segment '{segment.segment_id}' has label '{segment.label}'."
                ),
                series=series,
                state=state,
                legality_check=legality,
                metadata={"segmentId": segment_id, "parameters": dict(parameters or {})},
            )

        try:
            edited_series = self._apply_transform(
                normalized_operation,
                series,
                segment.start_index,
                segment.end_index,
                parameters or {},
            )
        except SignalTransformError as exc:
            return self._deny(
                operation_type=normalized_operation,
                reason_code="INVALID_PARAMETERS",
                message=str(exc),
                series=series,
                state=state,
                legality_check=legality,
                metadata={"segmentId": segment_id, "parameters": dict(parameters or {})},
            )

        constraint_evaluation = self._constraint_engine.evaluate(
            edited_series,
            [entry.to_dict() for entry in state.currentSnapshot.segments],
            operation_id=f"{state.stateId}-{normalized_operation}-{state.currentVersion}",
            constraint_mode=constraint_mode,
        )
        if constraint_evaluation.status == "FAIL":
            return self._deny(
                operation_type=normalized_operation,
                reason_code="CONSTRAINT_FAIL",
                message="Value operation violated one or more hard constraints.",
                series=series,
                state=state,
                legality_check=legality,
                constraint_evaluation=constraint_evaluation,
                metadata={"segmentId": segment_id, "parameters": dict(parameters or {})},
            )

        return ValueOperationResult(
            schemaVersion="1.0.0",
            operationType=normalized_operation,
            status="APPLIED",
            reasonCode=constraint_evaluation.status,
            message=f"Value operation '{normalized_operation}' applied successfully.",
            editedSeries=edited_series,
            state=state,
            constraintEvaluation=constraint_evaluation,
            legalityCheck=legality,
            metadata={"segmentId": segment_id, "parameters": dict(parameters or {})},
        )

    def _apply_transform(
        self,
        operation_type: str,
        series: Any,
        start_index: int,
        end_index: int,
        parameters: dict[str, Any],
    ) -> Any:
        if operation_type == "shift_level":
            delta = float(parameters.get("delta", 0.0))
            if delta == 0.0:
                raise SignalTransformError("ShiftLevel requires a non-zero delta.")
            return shift_level(series, start_index, end_index, delta=delta)
        if operation_type == "change_slope":
            slope_delta = float(parameters.get("slopeDelta", 0.0))
            if slope_delta == 0.0:
                raise SignalTransformError("ChangeSlope requires a non-zero slopeDelta.")
            return change_slope(series, start_index, end_index, slope_delta=slope_delta)
        if operation_type == "scale_spike":
            scale_factor = float(parameters.get("scaleFactor", 1.0))
            if scale_factor == 1.0:
                raise SignalTransformError("ScaleSpike requires a scaleFactor different from 1.0.")
            return scale_spike(series, start_index, end_index, scale_factor=scale_factor)
        if operation_type == "suppress_spike":
            return suppress_spike(series, start_index, end_index)
        if operation_type == "shift_event":
            offset = int(parameters.get("offset", 0))
            if offset == 0:
                raise SignalTransformError("ShiftEvent requires a non-zero offset.")
            return shift_event(series, start_index, end_index, offset=offset)
        if operation_type == "remove_event":
            return remove_event(series, start_index, end_index)
        raise ValueOperationError(f"Unsupported value operation '{operation_type}'.")

    def _find_segment(self, state: SegmentationState, segment_id: str):
        for segment in state.currentSnapshot.segments:
            if segment.segment_id == segment_id:
                return segment
        raise ValueOperationError(f"Segment '{segment_id}' is not present in the current segmentation state.")

    def _deny(
        self,
        *,
        operation_type: str,
        reason_code: str,
        message: str,
        series: Any,
        state: SegmentationState,
        legality_check: OperationLegalityResult | None,
        constraint_evaluation: ConstraintEvaluationResult | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ValueOperationResult:
        return ValueOperationResult(
            schemaVersion="1.0.0",
            operationType=operation_type,
            status="DENY",
            reasonCode=reason_code,
            message=message,
            editedSeries=series,
            state=state,
            constraintEvaluation=constraint_evaluation,
            legalityCheck=legality_check,
            metadata=dict(metadata or {}),
        )
