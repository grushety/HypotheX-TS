import copy

import numpy as np
import pytest

from app.services.datasets import DatasetArtifactError, DatasetRegistry


def test_dataset_registry_lists_manifest_datasets():
    registry = DatasetRegistry()

    names = [item.name for item in registry.list_datasets()]

    assert names == ["GunPoint", "ECG200", "Wafer", "BasicMotions"]


def test_dataset_registry_loads_univariate_dataset():
    registry = DatasetRegistry()

    dataset = registry.load_dataset("GunPoint")

    assert dataset.summary.is_univariate is True
    assert dataset.train_series.shape == (50, 1, 150)
    assert dataset.test_series.shape == (150, 1, 150)
    assert dataset.train_labels.shape == (50,)
    assert dataset.test_labels.shape == (150,)
    assert dataset.summary.classes == ("2", "1")
    assert np.issubdtype(dataset.train_series.dtype, np.floating)


def test_dataset_registry_loads_multivariate_dataset():
    registry = DatasetRegistry()

    dataset = registry.load_dataset("BasicMotions")

    assert dataset.summary.is_multivariate is True
    assert dataset.train_series.shape == (40, 6, 100)
    assert dataset.test_series.shape == (40, 6, 100)
    assert dataset.summary.n_channels == 6
    assert dataset.summary.classes == ("Standing", "Running", "Walking", "Badminton")


def test_dataset_registry_raises_explicit_error_for_missing_artifact():
    manifest = copy.deepcopy(
        {
            "datasets": [
                {
                    "name": "GunPoint",
                    "status": "prepared",
                    "task_type": "classification",
                    "series_type": "univariate",
                    "dataset_dir": "datasets/GunPoint",
                    "raw_dir": "datasets/GunPoint/raw",
                    "processed_dir": "datasets/GunPoint/processed",
                    "metadata_path": "datasets/GunPoint/metadata.json",
                    "summary_path": "datasets/GunPoint/processed/summary.json",
                    "source_archive": "univariate_ts",
                    "source": "https://www.timeseriesclassification.com/description.php?Dataset=GunPoint",
                    "license": None,
                    "notes": "Canonical source is the Time Series Classification archive description page.",
                    "n_channels": 1,
                    "train_shape": [50, 1, 150],
                    "test_shape": [150, 1, 150],
                    "n_classes": 2,
                    "classes": ["2", "1"],
                    "export_format": "npy",
                    "tensor_layout": "n_samples x n_channels x series_length",
                    "artifacts": {
                        "train_series_path": "datasets/GunPoint/processed/missing-X_train.npy",
                        "train_labels_path": "datasets/GunPoint/processed/y_train.npy",
                        "test_series_path": "datasets/GunPoint/processed/X_test.npy",
                        "test_labels_path": "datasets/GunPoint/processed/y_test.npy",
                    },
                }
            ]
        }
    )
    registry = DatasetRegistry(manifest=manifest)

    with pytest.raises(DatasetArtifactError) as exc_info:
        registry.load_dataset("GunPoint")

    assert "missing" in str(exc_info.value).lower()
