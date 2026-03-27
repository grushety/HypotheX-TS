from flask import Blueprint, current_app, jsonify, request

from app.services.compatibility import CompatibilityValidator
from app.services.datasets import DatasetNotFoundError, DatasetRegistry, DatasetRegistryError
from app.services.inference import InferenceAdapterError, InferenceServiceError, PredictionService, SampleSelectionError
from app.services.models import ModelArtifactNotFoundError, ModelRegistry, ModelRegistryError

benchmarks_bp = Blueprint("benchmarks", __name__)


def _get_dataset_registry() -> DatasetRegistry:
    return current_app.config.get("DATASET_REGISTRY") or DatasetRegistry()


def _get_model_registry() -> ModelRegistry:
    return current_app.config.get("MODEL_REGISTRY") or ModelRegistry()


def _get_compatibility_validator() -> CompatibilityValidator:
    return current_app.config.get("COMPATIBILITY_VALIDATOR") or CompatibilityValidator(
        dataset_registry=_get_dataset_registry(),
        model_registry=_get_model_registry(),
    )


def _get_prediction_service() -> PredictionService:
    return current_app.config.get("PREDICTION_SERVICE") or PredictionService(
        dataset_registry=_get_dataset_registry(),
        model_registry=_get_model_registry(),
        compatibility_validator=_get_compatibility_validator(),
    )


@benchmarks_bp.get("/api/benchmarks/datasets")
def list_datasets():
    try:
        registry = _get_dataset_registry()
        payload = {"datasets": [_serialize_dataset_summary(item) for item in registry.list_datasets()]}
        return jsonify(payload)
    except DatasetRegistryError as exc:
        return jsonify({"error": str(exc)}), 500


@benchmarks_bp.get("/api/benchmarks/models")
def list_models():
    try:
        registry = _get_model_registry()
        payload = {
            "families": [_serialize_model_family(item) for item in registry.list_families()],
            "artifacts": [_serialize_model_artifact(item) for item in registry.list_artifacts()],
        }
        return jsonify(payload)
    except ModelRegistryError as exc:
        return jsonify({"error": str(exc)}), 500


@benchmarks_bp.get("/api/benchmarks/compatibility")
def validate_compatibility():
    dataset_name = request.args.get("dataset")
    artifact_id = request.args.get("artifact_id")
    if not dataset_name or not artifact_id:
        return jsonify({"error": "Query parameters 'dataset' and 'artifact_id' are required."}), 400

    validator = _get_compatibility_validator()
    result = validator.validate(dataset_name, artifact_id)
    return jsonify(
        {
            "dataset_name": result.dataset_name,
            "artifact_id": result.artifact_id,
            "is_compatible": result.is_compatible,
            "messages": list(result.messages),
        }
    )


@benchmarks_bp.get("/api/benchmarks/prediction")
def predict_sample():
    dataset_name = request.args.get("dataset")
    artifact_id = request.args.get("artifact_id")
    split = request.args.get("split")
    sample_index_raw = request.args.get("sample_index")

    if not dataset_name or not artifact_id or not split or sample_index_raw is None:
        return (
            jsonify(
                {
                    "error": (
                        "Query parameters 'dataset', 'artifact_id', 'split', and 'sample_index' are required."
                    )
                }
            ),
            400,
        )

    try:
        sample_index = int(sample_index_raw)
    except ValueError:
        return jsonify({"error": "Query parameter 'sample_index' must be an integer."}), 400

    service = _get_prediction_service()
    try:
        prediction = service.predict(
            dataset_name=dataset_name,
            artifact_id=artifact_id,
            split=split,
            sample_index=sample_index,
        )
    except (DatasetNotFoundError, ModelArtifactNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 404
    except (InferenceServiceError, InferenceAdapterError, SampleSelectionError) as exc:
        return jsonify({"error": str(exc)}), 400
    except (DatasetRegistryError, ModelRegistryError) as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify(
        {
            "dataset_name": prediction.dataset_name,
            "artifact_id": prediction.artifact_id,
            "split": prediction.split,
            "sample_index": prediction.sample_index,
            "predicted_label": prediction.predicted_label,
            "true_label": prediction.true_label,
            "scores": [
                {
                    "label": score.label,
                    "score": score.score,
                    "probability": score.probability,
                }
                for score in prediction.scores
            ],
        }
    )


def _serialize_dataset_summary(summary):
    return {
        "name": summary.name,
        "status": summary.status,
        "task_type": summary.task_type,
        "series_type": summary.series_type,
        "n_channels": summary.n_channels,
        "train_shape": list(summary.train_shape),
        "test_shape": list(summary.test_shape),
        "n_classes": summary.n_classes,
        "classes": list(summary.classes),
        "export_format": summary.export_format,
        "tensor_layout": summary.tensor_layout,
        "notes": summary.notes,
    }


def _serialize_model_family(family):
    return {
        "family": family.family,
        "display_name": family.display_name,
        "source_repository": family.source_repository,
        "supported_datasets": list(family.supported_datasets),
        "notes": family.notes,
    }


def _serialize_model_artifact(artifact):
    return {
        "artifact_id": artifact.artifact_id,
        "family": artifact.family,
        "display_name": artifact.display_name,
        "dataset": artifact.dataset,
        "status": artifact.status,
        "input_shape": list(artifact.input_shape),
        "label_space": list(artifact.label_space),
        "notes": artifact.notes,
    }
