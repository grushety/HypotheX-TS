import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DomainConfigError(RuntimeError):
    """Raised when domain configuration cannot be loaded safely."""


@dataclass(frozen=True)
class ConstraintDefault:
    default_mode: str
    description: str


@dataclass(frozen=True)
class DomainConfig:
    schema_version: str
    ontology_name: str
    active_chunk_types: tuple[str, ...]
    thresholds: dict[str, float]
    duration_limits: dict[str, int]
    legal_operations_by_chunk: dict[str, tuple[str, ...]]
    constraint_defaults: dict[str, ConstraintDefault]

    def get_legal_operations(self, chunk_type: str) -> tuple[str, ...]:
        try:
            return self.legal_operations_by_chunk[chunk_type]
        except KeyError as exc:
            raise DomainConfigError(f"Chunk type '{chunk_type}' is not active in the domain config.") from exc

    def get_constraint_default(self, constraint_id: str) -> ConstraintDefault:
        try:
            return self.constraint_defaults[constraint_id]
        except KeyError as exc:
            raise DomainConfigError(
                f"Constraint default '{constraint_id}' is not declared in the domain config."
            ) from exc


DEFAULT_DOMAIN_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "mvp-domain-config.json"
_ALLOWED_CHUNK_TYPES = {"trend", "plateau", "spike", "event", "transition", "periodic"}
_ALLOWED_CONSTRAINT_MODES = {"soft", "hard"}


def load_domain_config(path: Path = DEFAULT_DOMAIN_CONFIG_PATH) -> DomainConfig:
    payload = _read_payload(path)
    return _parse_domain_config(payload, path)


def _read_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DomainConfigError(f"Domain config file was not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DomainConfigError(f"Domain config file is not valid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise DomainConfigError(f"Domain config must decode to an object: {path}")

    return payload


def _parse_domain_config(payload: dict[str, Any], path: Path) -> DomainConfig:
    required_fields = (
        "schemaVersion",
        "ontologyName",
        "activeChunkTypes",
        "thresholds",
        "durationLimits",
        "legalOperationsByChunk",
        "constraintDefaults",
    )
    for field_name in required_fields:
        if field_name not in payload:
            raise DomainConfigError(f"Domain config is missing required field '{field_name}': {path}")

    active_chunk_types = _parse_active_chunk_types(payload["activeChunkTypes"], path)
    thresholds = _parse_numeric_mapping(payload["thresholds"], "thresholds", float, path)
    duration_limits = _parse_numeric_mapping(payload["durationLimits"], "durationLimits", int, path)
    legal_operations_by_chunk = _parse_operations_registry(
        payload["legalOperationsByChunk"], active_chunk_types, path
    )
    constraint_defaults = _parse_constraint_defaults(payload["constraintDefaults"], path)

    return DomainConfig(
        schema_version=str(payload["schemaVersion"]),
        ontology_name=str(payload["ontologyName"]),
        active_chunk_types=active_chunk_types,
        thresholds=thresholds,
        duration_limits=duration_limits,
        legal_operations_by_chunk=legal_operations_by_chunk,
        constraint_defaults=constraint_defaults,
    )


def _parse_active_chunk_types(value: Any, path: Path) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise DomainConfigError(f"Domain config field 'activeChunkTypes' must be a non-empty list: {path}")

    chunk_types = tuple(str(item) for item in value)
    invalid_chunk_types = [item for item in chunk_types if item not in _ALLOWED_CHUNK_TYPES]
    if invalid_chunk_types:
        raise DomainConfigError(
            f"Domain config declares unsupported chunk types {invalid_chunk_types}: {path}"
        )
    if len(set(chunk_types)) != len(chunk_types):
        raise DomainConfigError(f"Domain config contains duplicate chunk types in 'activeChunkTypes': {path}")

    return chunk_types


def _parse_numeric_mapping(value: Any, field_name: str, caster: type, path: Path) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        raise DomainConfigError(f"Domain config field '{field_name}' must be a non-empty object: {path}")

    parsed: dict[str, Any] = {}
    for key, item in value.items():
        try:
            parsed[str(key)] = caster(item)
        except (TypeError, ValueError) as exc:
            raise DomainConfigError(
                f"Domain config field '{field_name}' has a non-numeric value for '{key}': {path}"
            ) from exc
    return parsed


def _parse_operations_registry(
    value: Any,
    active_chunk_types: tuple[str, ...],
    path: Path,
) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, dict) or not value:
        raise DomainConfigError(f"Domain config field 'legalOperationsByChunk' must be a non-empty object: {path}")

    parsed: dict[str, tuple[str, ...]] = {}
    for chunk_type in active_chunk_types:
        operations = value.get(chunk_type)
        if not isinstance(operations, list) or not operations:
            raise DomainConfigError(
                f"Domain config is missing legal operations for chunk type '{chunk_type}': {path}"
            )
        parsed[chunk_type] = tuple(str(item) for item in operations)

    return parsed


def _parse_constraint_defaults(value: Any, path: Path) -> dict[str, ConstraintDefault]:
    if not isinstance(value, dict) or not value:
        raise DomainConfigError(f"Domain config field 'constraintDefaults' must be a non-empty object: {path}")

    parsed: dict[str, ConstraintDefault] = {}
    for constraint_id, entry in value.items():
        if not isinstance(entry, dict):
            raise DomainConfigError(
                f"Constraint default '{constraint_id}' must be an object in the domain config: {path}"
            )
        default_mode = str(entry.get("defaultMode", ""))
        description = str(entry.get("description", ""))
        if default_mode not in _ALLOWED_CONSTRAINT_MODES:
            raise DomainConfigError(
                f"Constraint default '{constraint_id}' has unsupported mode '{default_mode}': {path}"
            )
        if not description:
            raise DomainConfigError(
                f"Constraint default '{constraint_id}' must include a non-empty description: {path}"
            )
        parsed[str(constraint_id)] = ConstraintDefault(
            default_mode=default_mode,
            description=description,
        )

    return parsed
