from app.schemas.compatibility import CompatibilityResult
from app.services.compatibility import CompatibilityValidator
from app.services.datasets import DatasetRegistry
from app.services.models import ModelRegistry


def test_compatibility_validator_accepts_matching_dataset_and_model():
    validator = CompatibilityValidator()

    result = validator.validate("GunPoint", "fcn-gunpoint")

    assert result == CompatibilityResult(
        dataset_name="GunPoint",
        artifact_id="fcn-gunpoint",
        is_compatible=True,
        messages=(),
    )


def test_compatibility_validator_rejects_unknown_dataset_name():
    validator = CompatibilityValidator()

    result = validator.validate("UnknownDataset", "fcn-gunpoint")

    assert result.is_compatible is False
    assert result.messages == ("Dataset 'UnknownDataset' is not declared in the benchmark manifest.",)


def test_compatibility_validator_rejects_multivariate_dataset_against_univariate_artifact():
    validator = CompatibilityValidator()

    result = validator.validate("BasicMotions", "fcn-gunpoint")

    assert result.is_compatible is False
    assert "declared for dataset 'GunPoint'" in result.messages[0]
    assert "multivariate with 6 channels" in result.messages[1]
    assert "expects length 150" in result.messages[2]


def test_compatibility_validator_checks_manifest_level_family_support():
    dataset_registry = DatasetRegistry(
        manifest={
            "datasets": [
                {
                    "name": "BasicMotions",
                    "status": "prepared",
                    "task_type": "classification",
                    "series_type": "multivariate",
                    "dataset_dir": "datasets/BasicMotions",
                    "raw_dir": "datasets/BasicMotions/raw",
                    "processed_dir": "datasets/BasicMotions/processed",
                    "metadata_path": "datasets/BasicMotions/metadata.json",
                    "summary_path": "datasets/BasicMotions/processed/summary.json",
                    "source_archive": "multivariate_ts",
                    "source": "https://www.timeseriesclassification.com/description.php?Dataset=BasicMotions",
                    "license": None,
                    "notes": "test dataset",
                    "n_channels": 6,
                    "train_shape": [40, 6, 100],
                    "test_shape": [40, 6, 100],
                    "n_classes": 4,
                    "classes": ["Standing", "Running", "Walking", "Badminton"],
                    "export_format": "npy",
                    "tensor_layout": "n_samples x n_channels x series_length",
                    "artifacts": {
                        "train_series_path": "datasets/BasicMotions/processed/X_train.npy",
                        "train_labels_path": "datasets/BasicMotions/processed/y_train.npy",
                        "test_series_path": "datasets/BasicMotions/processed/X_test.npy",
                        "test_labels_path": "datasets/BasicMotions/processed/y_test.npy",
                    },
                }
            ]
        }
    )
    model_registry = ModelRegistry(
        manifest={
            "families": [
                {
                    "family": "fcn",
                    "display_name": "FCN",
                    "source_repository": "dl-4-tsc",
                    "source_repository_path": "models/repos/dl-4-tsc",
                    "weights_root": "models/weights/fcn",
                    "supported_datasets": ["GunPoint"],
                    "notes": "test family",
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "fcn-basicmotions",
                    "family": "fcn",
                    "display_name": "FCN",
                    "dataset": "BasicMotions",
                    "status": "expected",
                    "artifact_dir": "models/weights/fcn/BasicMotions",
                    "source_repository": "dl-4-tsc",
                    "source_repository_path": "models/repos/dl-4-tsc",
                    "input_shape": [6, 100],
                    "label_space": ["Standing", "Running", "Walking", "Badminton"],
                    "notes": "test artifact",
                }
            ],
        }
    )
    validator = CompatibilityValidator(
        dataset_registry=dataset_registry,
        model_registry=model_registry,
    )

    result = validator.validate("BasicMotions", "fcn-basicmotions")

    assert result.is_compatible is False
    assert result.messages == (
        "Model family 'FCN' does not support dataset 'BasicMotions'. Supported datasets: GunPoint.",
    )
