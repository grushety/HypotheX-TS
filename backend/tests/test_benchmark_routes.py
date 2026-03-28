import json
from pathlib import Path

import numpy as np

from app.config import TestingConfig
from app.factory import create_app
from app.services.compatibility import CompatibilityValidator
from app.services.datasets import DatasetRegistry
from app.services.inference import PredictionService
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


def create_benchmark_client(tmp_path):
    dataset_registry = DatasetRegistry(manifest=create_dataset_manifest(tmp_path))
    model_registry = ModelRegistry(manifest=create_model_manifest(tmp_path))
    compatibility_validator = CompatibilityValidator(
        dataset_registry=dataset_registry,
        model_registry=model_registry,
    )
    prediction_service = PredictionService(
        dataset_registry=dataset_registry,
        model_registry=model_registry,
        compatibility_validator=compatibility_validator,
    )

    app = create_app(TestingConfig)
    app.config["DATASET_REGISTRY"] = dataset_registry
    app.config["MODEL_REGISTRY"] = model_registry
    app.config["COMPATIBILITY_VALIDATOR"] = compatibility_validator
    app.config["PREDICTION_SERVICE"] = prediction_service
    return app.test_client()


def test_dataset_list_endpoint_returns_stable_schema(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.get("/api/benchmarks/datasets")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {
        "datasets": [
            {
                "name": "GunPoint",
                "status": "prepared",
                "task_type": "classification",
                "series_type": "univariate",
                "n_channels": 1,
                "train_shape": [2, 1, 3],
                "test_shape": [2, 1, 3],
                "n_classes": 2,
                "classes": ["class-0", "class-1"],
                "export_format": "npy",
                "tensor_layout": "n_samples x n_channels x series_length",
                "notes": "test dataset",
            }
        ]
    }


def test_model_list_endpoint_returns_families_and_artifacts(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.get("/api/benchmarks/models")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["families"] == [
        {
            "family": "fcn",
            "display_name": "FCN",
            "source_repository": "dl-4-tsc",
            "supported_datasets": ["GunPoint"],
            "notes": "test family",
        }
    ]
    assert payload["artifacts"] == [
        {
            "artifact_id": "fcn-gunpoint",
            "family": "fcn",
            "display_name": "FCN",
            "dataset": "GunPoint",
            "status": "ready",
            "input_shape": [1, 3],
            "label_space": ["class-0", "class-1"],
            "notes": "test artifact",
        }
    ]


def test_compatibility_endpoint_reports_incompatible_pair(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.get("/api/benchmarks/compatibility?dataset=Unknown&artifact_id=fcn-gunpoint")

    assert response.status_code == 200
    assert response.get_json() == {
        "dataset_name": "Unknown",
        "artifact_id": "fcn-gunpoint",
        "is_compatible": False,
        "messages": ["Dataset 'Unknown' is not declared in the benchmark manifest."],
    }


def test_prediction_endpoint_returns_normalized_prediction_schema(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.get(
        "/api/benchmarks/prediction?dataset=GunPoint&artifact_id=fcn-gunpoint&split=test&sample_index=0"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["dataset_name"] == "GunPoint"
    assert payload["artifact_id"] == "fcn-gunpoint"
    assert payload["split"] == "test"
    assert payload["sample_index"] == 0
    assert payload["predicted_label"] == "class-0"
    assert payload["true_label"] == "class-0"
    assert len(payload["scores"]) == 2


def test_sample_endpoint_returns_real_sample_payload(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.get("/api/benchmarks/sample?dataset=GunPoint&split=test&sample_index=1")

    assert response.status_code == 200
    assert response.get_json() == {
        "dataset_name": "GunPoint",
        "dataset_id": "GunPoint",
        "split": "test",
        "sample_index": 1,
        "task_type": "classification",
        "series_type": "univariate",
        "channel_count": 1,
        "series_length": 3,
        "label": "class-1",
        "values": [[0.8999999761581421, 1.0, 0.800000011920929]],
    }
