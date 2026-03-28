from dataclasses import dataclass
from typing import Any

from app.core.domain_config import DomainConfig, load_domain_config


@dataclass(frozen=True)
class OperationRegistryCatalog:
    schemaVersion: str
    ontologyName: str
    operationsByChunk: dict[str, tuple[str, ...]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schemaVersion,
            "ontologyName": self.ontologyName,
            "operationsByChunk": {
                chunk_type: list(operations)
                for chunk_type, operations in self.operationsByChunk.items()
            },
        }


def get_legal_operations_for_chunk(
    chunk_type: str,
    *,
    domain_config: DomainConfig | None = None,
) -> tuple[str, ...]:
    config = domain_config or load_domain_config()
    return config.get_legal_operations(chunk_type)


def build_operation_registry_catalog(
    *,
    domain_config: DomainConfig | None = None,
) -> OperationRegistryCatalog:
    config = domain_config or load_domain_config()
    return OperationRegistryCatalog(
        schemaVersion="1.0.0",
        ontologyName=config.ontology_name,
        operationsByChunk={
            chunk_type: config.get_legal_operations(chunk_type)
            for chunk_type in config.active_chunk_types
        },
    )
