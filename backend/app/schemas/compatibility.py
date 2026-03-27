from dataclasses import dataclass


@dataclass(frozen=True)
class CompatibilityResult:
    dataset_name: str
    artifact_id: str
    is_compatible: bool
    messages: tuple[str, ...]
