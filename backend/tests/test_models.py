import copy

import pytest

from app.services.models import ModelArtifactValidationError, ModelRegistry


def test_model_registry_lists_manifest_artifacts():
    registry = ModelRegistry()

    family_names = [item.family for item in registry.list_families()]
    artifact_ids = [item.artifact_id for item in registry.list_artifacts()]

    assert family_names == ["fcn", "mlp", "inceptiontime"]
    assert "fcn-gunpoint" in artifact_ids
    assert "inceptiontime-basicmotions" in artifact_ids


def test_model_registry_loads_valid_artifact_from_custom_manifest(tmp_path):
    artifact_dir = tmp_path / "models" / "weights" / "fcn" / "GunPoint"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "metadata.json").write_text('{"family":"fcn"}', encoding="utf-8")
    (artifact_dir / "best_model.keras").write_text("stub", encoding="utf-8")

    manifest = {
        "families": [
            {
                "family": "fcn",
                "display_name": "FCN",
                "source_repository": "dl-4-tsc",
                "source_repository_path": str(tmp_path / "models" / "repos" / "dl-4-tsc"),
                "weights_root": str(tmp_path / "models" / "weights" / "fcn"),
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
                "source_repository_path": str(tmp_path / "models" / "repos" / "dl-4-tsc"),
                "input_shape": [1, 150],
                "label_space": ["2", "1"],
                "notes": "test artifact",
            }
        ],
    }

    registry = ModelRegistry(manifest=manifest)
    handle = registry.load_artifact("fcn-gunpoint")

    assert handle.artifact.family == "fcn"
    assert handle.artifact.input_shape == (1, 150)
    assert handle.checkpoint_path == artifact_dir / "best_model.keras"
    assert handle.metadata_path == artifact_dir / "metadata.json"


def test_model_registry_fails_fast_for_missing_required_files(tmp_path):
    artifact_dir = tmp_path / "models" / "weights" / "inceptiontime" / "Wafer"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "metadata.json").write_text('{"family":"inceptiontime"}', encoding="utf-8")

    manifest = {
        "families": [
            {
                "family": "inceptiontime",
                "display_name": "InceptionTime",
                "source_repository": "InceptionTime",
                "source_repository_path": str(tmp_path / "models" / "repos" / "InceptionTime"),
                "weights_root": str(tmp_path / "models" / "weights" / "inceptiontime"),
                "supported_datasets": ["Wafer"],
                "notes": "test family",
            }
        ],
        "artifacts": [
            {
                "artifact_id": "inceptiontime-wafer",
                "family": "inceptiontime",
                "display_name": "InceptionTime",
                "dataset": "Wafer",
                "status": "ready",
                "artifact_dir": str(artifact_dir),
                "source_repository": "InceptionTime",
                "source_repository_path": str(tmp_path / "models" / "repos" / "InceptionTime"),
                "input_shape": [1, 152],
                "label_space": ["1", "-1"],
                "notes": "test artifact",
            }
        ],
    }

    registry = ModelRegistry(manifest=copy.deepcopy(manifest))

    with pytest.raises(ModelArtifactValidationError) as exc_info:
        registry.load_artifact("inceptiontime-wafer")

    assert "checkpoint" in str(exc_info.value).lower()
