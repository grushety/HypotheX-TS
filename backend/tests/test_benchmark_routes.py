import json

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


def test_operation_registry_endpoint_returns_chunk_operation_catalog(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.get("/api/benchmarks/operation-registry")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["schemaVersion"] == "1.0.0"
    assert payload["ontologyName"] == "mvp-core"
    assert payload["operationsByChunk"]["trend"] == [
        "change_slope",
        "reverse_trend",
        "shift_in_time",
        "extend",
        "shorten",
        "split",
        "merge",
    ]
    assert payload["operationsByChunk"]["event"] == [
        "shift_in_time",
        "change_duration",
        "change_intensity",
        "remove",
        "duplicate",
        "split",
        "merge",
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


def test_prediction_endpoint_surfaces_transform_chain_and_input_length(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.get(
        "/api/benchmarks/prediction?dataset=GunPoint&artifact_id=fcn-gunpoint&split=test&sample_index=0"
    )

    assert response.status_code == 200
    payload = response.get_json()
    # GunPoint sample is stored as float32 (1, 3) → cast_float64 then flatten.
    assert payload["model_input_length"] == 3
    names = [t["name"] for t in payload["transforms"]]
    assert names == ["cast_float64", "flatten"]
    cast = payload["transforms"][0]
    assert cast["params"]["from_dtype"] == "float32"
    assert cast["params"]["to_dtype"] == "float64"
    assert cast["before_shape"] == [1, 3]
    assert cast["after_shape"] == [1, 3]
    flatten = payload["transforms"][1]
    assert flatten["before_shape"] == [1, 3]
    assert flatten["after_shape"] == [3]
    assert flatten["params"]["order"] == "C"


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


def test_suggestion_endpoint_returns_serializable_suggestion_payload(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.get("/api/benchmarks/suggestion?dataset=GunPoint&split=test&sample_index=1")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["schemaVersion"] == "1.0.0"
    assert payload["suggestionId"] == "suggestion-GunPoint-test-1"
    assert payload["seriesId"] == "GunPoint:test:1"
    assert payload["modelVersion"] == "suggestion-model-v1"
    assert isinstance(payload["candidateBoundaries"], list)
    assert len(payload["provisionalSegments"]) >= 1
    assert "label" in payload["provisionalSegments"][0]
    assert "labelScores" in payload["provisionalSegments"][0]


def test_suggestion_endpoint_default_labeler_is_prototype(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.get("/api/benchmarks/suggestion?dataset=GunPoint&split=test&sample_index=0")

    assert response.status_code == 200
    assert response.get_json()["labeler"] == "prototype"


def test_suggestion_endpoint_labeler_prototype_explicit(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.get(
        "/api/benchmarks/suggestion?dataset=GunPoint&split=test&sample_index=0&labeler=prototype"
    )

    assert response.status_code == 200
    assert response.get_json()["labeler"] == "prototype"


def test_suggestion_endpoint_labeler_llm_returns_llm_in_response(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.get(
        "/api/benchmarks/suggestion?dataset=GunPoint&split=test&sample_index=0&labeler=llm"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["labeler"] == "llm"
    assert len(payload["provisionalSegments"]) >= 1


def test_suggestion_endpoint_unknown_labeler_defaults_to_prototype(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.get(
        "/api/benchmarks/suggestion?dataset=GunPoint&split=test&sample_index=0&labeler=unknown_xyz"
    )

    assert response.status_code == 200
    assert response.get_json()["labeler"] == "prototype"


def test_predict_values_endpoint_reports_empty_transform_chain_on_1d_floats(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.post(
        "/api/benchmarks/predict-values",
        data=json.dumps({"artifact_id": "fcn-gunpoint", "values": [0.1, 0.2, 0.3]}),
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.get_json()
    # JSON floats arrive as float64 1-D — no cast, no flatten. The strip
    # should honestly report "0 transforms · identity".
    assert payload["transforms"] == []
    assert payload["model_input_length"] == 3


def test_evidence_plausibility_endpoint_rejects_missing_dataset(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.post(
        "/api/benchmarks/evidence/plausibility",
        data=json.dumps(
            {
                "baseline_values": [0.0, 0.1],
                "current_values": [0.0, 0.2],
                "target_class": "class-0",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "dataset" in response.get_json()["error"].lower()


def test_evidence_plausibility_endpoint_rejects_mismatched_lengths(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.post(
        "/api/benchmarks/evidence/plausibility",
        data=json.dumps(
            {
                "dataset": "GunPoint",
                "baseline_values": [0.0, 0.1, 0.2],
                "current_values": [0.0, 0.2],
                "target_class": "class-0",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 400
    error = response.get_json()["error"].lower()
    assert "length" in error or "match" in error


def test_evidence_plausibility_endpoint_returns_proximity_sparsity_and_null_plausibility(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.post(
        "/api/benchmarks/evidence/plausibility",
        data=json.dumps(
            {
                "dataset": "GunPoint",
                "baseline_values": [0.0, 0.0, 0.0],
                "current_values": [0.0, 0.5, 0.0],
                "target_class": "class-0",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.get_json()
    # proximity + sparsity always returned (no calibration required)
    assert isinstance(payload["proximity"], float)
    assert isinstance(payload["sparsity"], float)
    assert 0.0 <= payload["sparsity"] <= 1.0
    # proximity_pct is None — no calibration cache exists for "GunPoint".
    assert payload["proximity_pct"] is None
    assert payload["too_dense"] is False
    # yNN index cannot be built from the (2, 1, 3) test fixture (ndim != 2);
    # plausibility is honestly null rather than a fabricated number.
    assert payload["plausibility"] is None
    assert payload["plausibility_k"] is None


def test_saliency_endpoint_rejects_missing_values(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.post(
        "/api/benchmarks/saliency",
        data=json.dumps({"artifact_id": "fcn-gunpoint"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "values" in response.get_json()["error"].lower()


def test_saliency_endpoint_rejects_non_finite_values(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.post(
        "/api/benchmarks/saliency",
        data=json.dumps(
            {"artifact_id": "fcn-gunpoint", "values": [0.1, float("inf"), 0.2]}
        ),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "finite" in response.get_json()["error"].lower()


def test_saliency_endpoint_returns_per_timestep_attribution_aligned_to_input(tmp_path):
    client = create_benchmark_client(tmp_path)
    # Asymmetric input so attribution isn't flat zero. Prototypes are
    # [0,0,0] (class-0) and [1,1,1] (class-1); baseline [0.1, 0, 0.4]
    # classifies as class-0 (sum = 0.5 < 1.5).
    response = client.post(
        "/api/benchmarks/saliency",
        data=json.dumps(
            {"artifact_id": "fcn-gunpoint", "values": [0.1, 0.0, 0.4]}
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["baseline_class"] == "class-0"
    assert isinstance(payload["attribution"], list)
    assert len(payload["attribution"]) == 3
    assert all(isinstance(v, float) for v in payload["attribution"])
    # Method label + reference are surfaced (REWORK-08 AC).
    assert "occlusion" in payload["method"].lower()
    assert payload["reference"]
    # At least one timestep must have a non-zero attribution — masking
    # something has to change the predicted-class probability for a real
    # classifier with non-degenerate input.
    assert any(abs(v) > 1e-9 for v in payload["attribution"])


def test_min_flip_endpoint_rejects_missing_artifact_id(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.post(
        "/api/operations/min-flip",
        data=json.dumps({"baseline_values": [0.0, 0.0, 0.0]}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "artifact_id" in response.get_json()["error"].lower()


def test_min_flip_endpoint_rejects_non_finite_baseline(tmp_path):
    client = create_benchmark_client(tmp_path)

    response = client.post(
        "/api/operations/min-flip",
        data=json.dumps(
            {"artifact_id": "fcn-gunpoint", "baseline_values": [0.1, float("nan"), 0.0]}
        ),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "finite" in response.get_json()["error"].lower()


def test_min_flip_endpoint_returns_closed_form_flip_for_prototype_classifier(tmp_path):
    client = create_benchmark_client(tmp_path)
    # Prototypes in the fixture are [0,0,0] (class-0) and [1,1,1] (class-1).
    # Baseline [0.1, 0.0, 0.1] is closer to class-0; the closed-form flip
    # crosses the perpendicular bisector (x1 + x2 + x3 = 1.5) toward class-1.
    response = client.post(
        "/api/operations/min-flip",
        data=json.dumps(
            {"artifact_id": "fcn-gunpoint", "baseline_values": [0.1, 0.0, 0.1]}
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["found"] is True
    assert payload["baseline_class"] == "class-0"
    assert payload["flipped_class"] == "class-1"
    # Distance to the bisector: signed_distance = (||p0||² - ||p1||²)/2 maths.
    # ((p0 - p1)·x - ((|p0|² - |p1|²)/2)) / |p0 - p1|
    # = ((-1,-1,-1)·(0.1,0,0.1) - (0 - 3)/2) / sqrt(3)
    # = (-0.2 - (-1.5)) / sqrt(3) = 1.3 / sqrt(3) ≈ 0.7506
    expected = 1.3 / (3 ** 0.5)
    assert abs(payload["distance"] - expected) < 1e-6
    # Edit lives just past the boundary toward class-1 — every coordinate
    # bumps by roughly the same amount in the +1 direction.
    edit = payload["edit_values"]
    assert len(edit) == 3
    assert all(e > b for e, b in zip(edit, [0.1, 0.0, 0.1]))
    # Method + reference are surfaced for provenance.
    assert "closed-form" in payload["method"]
    assert "Wachter" in payload["reference"]
    assert payload["reason"] is None
