from dataclasses import dataclass
from typing import Any

from app.domain.state_models import SegmentationState
from app.domain.validation import OperationLegalityResult
from app.services.constraint_engine import ConstraintEvaluationResult


@dataclass(frozen=True)
class OperationResultEnvelope:
    schemaVersion: str
    operationType: str
    status: str
    applied: bool
    reasonCode: str
    message: str
    state: SegmentationState
    constraintEvaluation: ConstraintEvaluationResult | None
    legalityChecks: tuple[OperationLegalityResult, ...]
    metadata: dict[str, Any]
    editedSeries: Any | None = None

    @property
    def violations(self) -> tuple[Any, ...]:
        if self.constraintEvaluation is None:
            return ()
        return self.constraintEvaluation.violations

    @property
    def constraintMode(self) -> str | None:
        if self.constraintEvaluation is None:
            return None
        return self.constraintEvaluation.constraintMode

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schemaVersion": self.schemaVersion,
            "operationType": self.operationType,
            "status": self.status,
            "applied": self.applied,
            "reasonCode": self.reasonCode,
            "message": self.message,
            "constraintMode": self.constraintMode,
            "violations": [violation.to_dict() for violation in self.violations],
            "state": self.state.to_dict(),
            "legalityChecks": [entry.to_dict() for entry in self.legalityChecks],
            "metadata": dict(self.metadata),
        }
        if self.constraintEvaluation is not None:
            payload["constraintEvaluation"] = self.constraintEvaluation.to_dict()
        if self.editedSeries is not None:
            payload["editedSeries"] = self._serialize_series(self.editedSeries)
        return payload

    def _serialize_series(self, series: Any) -> Any:
        return series.tolist() if hasattr(series, "tolist") else series
