from dataclasses import dataclass
from typing import Any

from app.core.domain_config import DomainConfig, DomainConfigError, load_domain_config
from app.domain.operations_registry import get_legal_operations_for_chunk


@dataclass(frozen=True)
class OperationLegalityResult:
    schemaVersion: str
    ontologyName: str
    chunkType: str
    requestedOperation: str
    status: str
    reasonCode: str
    message: str
    validOperations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schemaVersion,
            "ontologyName": self.ontologyName,
            "chunkType": self.chunkType,
            "requestedOperation": self.requestedOperation,
            "status": self.status,
            "reasonCode": self.reasonCode,
            "message": self.message,
            "validOperations": list(self.validOperations),
        }


def validate_operation_legality(
    chunk_type: str,
    requested_operation: str,
    *,
    domain_config: DomainConfig | None = None,
) -> OperationLegalityResult:
    config = domain_config or load_domain_config()

    try:
        valid_operations = get_legal_operations_for_chunk(chunk_type, domain_config=config)
    except DomainConfigError:
        return OperationLegalityResult(
            schemaVersion="1.0.0",
            ontologyName=config.ontology_name,
            chunkType=chunk_type,
            requestedOperation=requested_operation,
            status="DENY",
            reasonCode="UNKNOWN_CHUNK_TYPE",
            message=f"Chunk type '{chunk_type}' is not active in the current ontology.",
            validOperations=(),
        )

    if requested_operation in valid_operations:
        return OperationLegalityResult(
            schemaVersion="1.0.0",
            ontologyName=config.ontology_name,
            chunkType=chunk_type,
            requestedOperation=requested_operation,
            status="ALLOW",
            reasonCode="LEGAL",
            message=f"Operation '{requested_operation}' is legal for chunk type '{chunk_type}'.",
            validOperations=valid_operations,
        )

    return OperationLegalityResult(
        schemaVersion="1.0.0",
        ontologyName=config.ontology_name,
        chunkType=chunk_type,
        requestedOperation=requested_operation,
        status="DENY",
        reasonCode="OPERATION_NOT_ALLOWED",
        message=f"Operation '{requested_operation}' is not legal for chunk type '{chunk_type}'.",
        validOperations=valid_operations,
    )
