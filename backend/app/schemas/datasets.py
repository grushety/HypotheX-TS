from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class DatasetArtifactPaths:
    train_series_path: Path
    train_labels_path: Path
    test_series_path: Path
    test_labels_path: Path


@dataclass(frozen=True)
class DatasetSummary:
    name: str
    status: str
    task_type: str
    series_type: str
    dataset_dir: Path
    raw_dir: Path
    processed_dir: Path
    metadata_path: Path
    summary_path: Path
    source_archive: str
    source: str
    license_name: str | None
    notes: str
    n_channels: int
    train_shape: tuple[int, ...]
    test_shape: tuple[int, ...]
    n_classes: int
    classes: tuple[str, ...]
    export_format: str
    tensor_layout: str
    artifacts: DatasetArtifactPaths

    @property
    def is_univariate(self) -> bool:
        return self.series_type == "univariate"

    @property
    def is_multivariate(self) -> bool:
        return self.series_type == "multivariate"


@dataclass(frozen=True)
class LoadedDataset:
    summary: DatasetSummary
    train_series: np.ndarray
    train_labels: np.ndarray
    test_series: np.ndarray
    test_labels: np.ndarray
