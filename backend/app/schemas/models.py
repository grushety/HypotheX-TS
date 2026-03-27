from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelFamilyDescriptor:
    family: str
    display_name: str
    source_repository: str
    source_repository_path: Path
    weights_root: Path
    supported_datasets: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class ModelArtifactDescriptor:
    artifact_id: str
    family: str
    display_name: str
    dataset: str
    status: str
    artifact_dir: Path
    source_repository: str
    source_repository_path: Path
    input_shape: tuple[int, ...]
    label_space: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class ModelArtifactHandle:
    artifact: ModelArtifactDescriptor
    checkpoint_path: Path
    metadata_path: Path

