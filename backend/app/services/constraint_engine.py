from dataclasses import dataclass
from typing import Any

from app.core.domain_config import DomainConfig, load_domain_config
from app.domain.constraints import ConstraintViolation, evaluate_constraints


@dataclass(frozen=True)
class ConstraintEvaluationResult:
    schemaVersion: str
    evaluationId: str
    operationId: str
    constraintMode: str
    status: str
    violations: tuple[ConstraintViolation, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schemaVersion,
            "evaluationId": self.evaluationId,
            "operationId": self.operationId,
            "constraintMode": self.constraintMode,
            "status": self.status,
            "violations": [violation.to_dict() for violation in self.violations],
        }


class ConstraintEngine:
    def __init__(self, domain_config: DomainConfig | None = None):
        self._domain_config = domain_config or load_domain_config()

    def evaluate(
        self,
        series: Any,
        segments: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        *,
        operation_id: str,
        constraint_mode: str | None = None,
    ) -> ConstraintEvaluationResult:
        violations = evaluate_constraints(
            series,
            segments,
            domain_config=self._domain_config,
            constraint_mode=constraint_mode,
        )
        resolved_mode = self._resolve_constraint_mode(violations, constraint_mode)
        status = self._resolve_status(violations, resolved_mode)

        return ConstraintEvaluationResult(
            schemaVersion="1.0.0",
            evaluationId=f"constraint-eval-{operation_id}",
            operationId=operation_id,
            constraintMode=resolved_mode,
            status=status,
            violations=violations,
        )

    def _resolve_constraint_mode(
        self,
        violations: tuple[ConstraintViolation, ...],
        constraint_mode: str | None,
    ) -> str:
        if constraint_mode is not None:
            return constraint_mode
        if any(violation.severity == "hard" for violation in violations):
            return "hard"
        return "soft"

    def _resolve_status(
        self,
        violations: tuple[ConstraintViolation, ...],
        constraint_mode: str,
    ) -> str:
        if not violations:
            return "PASS"
        if constraint_mode == "hard":
            return "FAIL"
        return "WARN"
