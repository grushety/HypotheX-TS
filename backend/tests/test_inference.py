import json
from pathlib import Path

import numpy as np
import pytest

from app.services.compatibility import CompatibilityValidator
from app.services.datasets import DatasetRegistry
from app.services.inference import InferenceAdapterError, PredictionService
from app.services.models import ModelRegistry


def create_dataset_manifest(tmp_path):
    dataset_dir = tmp_path / "benchmarks" / "datasets" / "GunPoint" / "processed"
    dataset_dir.mkdir(parents=True)
    train_series = np.asarray(
        [
            [[0.0, 0.0, 0.0]],
            [[1.0, 1.0, 1.0]],
        ],
        dtype=np.float32,
    )
    train_labels = np.asarray([0, 1], dtype=np.int64)
    test_series = np.asarray(
        [
            [[0.1, 0.0, 0.1]],
            [[0.9, 1.0, 0.8]],
        ],
        dtype=np.float32,
    )
    test_labels = np.asarray([0, 1], dtype=np.int64)

    np.save(dataset_dir / "X_train.npy", train_series)
    np.save(dataset_dir / "y_train.npy", train_labels)
    np.save(dataset_dir / "X_test.npy", test_series)
    np.save(dataset_dir / "y_test.npy", test_labels)

    return {
        "datasets": [
            {
                "name": "GunPoint",
                "status": "prepared",
                "task_type": "classification",
                "series_type": "univariate",
                "dataset_dir": str(tmp_path / "benchmarks" / "datasets" / "GunPoint"),
                "raw_dir": str(tmp_path / "benchmarks" / "datasets" / "GunPoint" / "raw"),
                "processed_dir": str(dataset_dir),
                "metadata_path": str(tmp_path / "benchmarks" / "datasets" / "GunPoint" / "metadata.json"),
                "summary_path": str(dataset_dir / "summary.json"),
                "source_archive": "univariate_ts",
                "source": "test source",
                "license": None,
                "notes": "test dataset",
                "n_channels": 1,
                "train_shape": [2, 1, 3],
                "test_shape": [2, 1, 3],
                "n_classes": 2,
                "classes": ["class-0", "class-1"],
                "export_format": "npy",
                "tensor_layout": "n_samples x n_channels x series_length",
                "artifacts": {
                    "train_series_path": str(dataset_dir / "X_train.npy"),
                    "train_labels_path": str(dataset_dir / "y_train.npy"),
                    "test_series_path": str(dataset_dir / "X_test.npy"),
                    "test_labels_path": str(dataset_dir / "y_test.npy"),
                },
            }
        ]
    }


def create_model_manifest(tmp_path):
    artifact_dir = tmp_path / "benchmarks" / "models" / "weights" / "fcn" / "GunPoint"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "best_model.keras").write_text("stub", encoding="utf-8")
    (artifact_dir / "metadata.json").write_text(
        json.dumps(
            {
                "inference_adapter": "nearest_prototype",
                "prototype_vectors": [
                    [0.0, 0.0, 0.0],
                    [1.0, 1.0, 1.0],
                ],
            }
        ),
        encoding="utf-8",
    )

    return {
        "families": [
            {
                "family": "fcn",
                "display_name": "FCN",
                "source_repository": "dl-4-tsc",
                "source_repository_path": str(tmp_path / "benchmarks" / "models" / "repos" / "dl-4-tsc"),
                "weights_root": str(tmp_path / "benchmarks" / "models" / "weights" / "fcn"),
                "supported_datasets": ["GunPoint"],
                "notes": "test family",
            }
        ],
        "artifacts": [
            {
                "artifact_id": "fcn-gunpoint",
                "family": "fcn",
                "display_name": "FCN",
                "dataset": "GunPoint",
                "status": "ready",
                "artifact_dir": str(artifact_dir),
                "source_repository": "dl-4-tsc",
                "source_repository_path": str(tmp_path / "benchmarks" / "models" / "repos" / "dl-4-tsc"),
                "input_shape": [1, 3],
                "label_space": ["class-0", "class-1"],
                "notes": "test artifact",
            }
        ],
    }


def test_prediction_service_runs_happy_path(tmp_path):
    dataset_registry = DatasetRegistry(manifest=create_dataset_manifest(tmp_path))
    model_registry = ModelRegistry(manifest=create_model_manifest(tmp_path))
    compatibility_validator = CompatibilityValidator(
        dataset_registry=dataset_registry,
        model_registry=model_registry,
    )
    service = PredictionService(
        dataset_registry=dataset_registry,
        model_registry=model_registry,
        compatibility_validator=compatibility_validator,
    )

    response = service.predict(
        dataset_name="GunPoint",
        artifact_id="fcn-gunpoint",
        split="test",
        sample_index=0,
    )

    assert response.dataset_name == "GunPoint"
    assert response.artifact_id == "fcn-gunpoint"
    assert response.split == "test"
    assert response.sample_index == 0
    assert response.predicted_label == "class-0"
    assert response.true_label == "class-0"
    assert len(response.scores) == 2
    assert response.scores[0].probability > response.scores[1].probability


def test_prediction_service_reports_adapter_failure(tmp_path):
    dataset_registry = DatasetRegistry(manifest=create_dataset_manifest(tmp_path))
    model_manifest = create_model_manifest(tmp_path)
    artifact_dir = model_manifest["artifacts"][0]["artifact_dir"]
    (Path(artifact_dir) / "metadata.json").write_text(
        json.dumps({"inference_adapter": "unsupported"}),
        encoding="utf-8",
    )
    model_registry = ModelRegistry(manifest=model_manifest)
    compatibility_validator = CompatibilityValidator(
        dataset_registry=dataset_registry,
        model_registry=model_registry,
    )
    service = PredictionService(
        dataset_registry=dataset_registry,
        model_registry=model_registry,
        compatibility_validator=compatibility_validator,
    )

    with pytest.raises(InferenceAdapterError) as exc_info:
        service.predict(
            dataset_name="GunPoint",
            artifact_id="fcn-gunpoint",
            split="test",
            sample_index=0,
        )

    assert "supported inference adapter" in str(exc_info.value)
