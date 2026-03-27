from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.core.benchmark_manifest import BenchmarkManifestError, load_model_manifest, resolve_benchmark_path
from app.schemas.models import ModelArtifactDescriptor, ModelArtifactHandle, ModelFamilyDescriptor


class ModelRegistryError(RuntimeError):
    """Base error for model registry failures."""


class ModelArtifactNotFoundError(ModelRegistryError):
    """Raised when a requested model artifact is not declared in the manifest."""


class ModelArtifactValidationError(ModelRegistryError):
    """Raised when an artifact directory is missing required files."""


class ModelArtifactAdapter:
    def __init__(self, family: str, checkpoint_candidates: tuple[str, ...]):
        self.family = family
        self.checkpoint_candidates = checkpoint_candidates

    def load(self, artifact: ModelArtifactDescriptor) -> ModelArtifactHandle:
        if not artifact.artifact_dir.exists():
            raise ModelArtifactValidationError(
                f"Model artifact directory does not exist for '{artifact.artifact_id}': {artifact.artifact_dir}"
            )
        if not artifact.artifact_dir.is_dir():
            raise ModelArtifactValidationError(
                f"Model artifact path is not a directory for '{artifact.artifact_id}': {artifact.artifact_dir}"
            )

        metadata_path = artifact.artifact_dir / "metadata.json"
        if not metadata_path.exists():
            raise ModelArtifactValidationError(
                f"Model artifact metadata.json is missing for '{artifact.artifact_id}': {metadata_path}"
            )

        checkpoint_path = self._resolve_checkpoint_path(artifact)
        return ModelArtifactHandle(
            artifact=artifact,
            checkpoint_path=checkpoint_path,
            metadata_path=metadata_path,
        )

    def _resolve_checkpoint_path(self, artifact: ModelArtifactDescriptor) -> Path:
        for filename in self.checkpoint_candidates:
            candidate = artifact.artifact_dir / filename
            if candidate.exists():
                return candidate

        expected = ", ".join(self.checkpoint_candidates)
        raise ModelArtifactValidationError(
            f"Model artifact checkpoint is missing for '{artifact.artifact_id}'. Expected one of: {expected}"
        )


class ModelRegistry:
    _ADAPTERS = {
        "fcn": ModelArtifactAdapter(
            family="fcn",
            checkpoint_candidates=("best_model.keras", "best_model.h5", "best_model.hdf5"),
        ),
        "mlp": ModelArtifactAdapter(
            family="mlp",
            checkpoint_candidates=("best_model.keras", "best_model.h5", "best_model.hdf5"),
        ),
        "inceptiontime": ModelArtifactAdapter(
            family="inceptiontime",
            checkpoint_candidates=("best_model.keras", "best_model.h5", "best_model.hdf5", "last_model.keras"),
        ),
    }

    def __init__(self, manifest: Mapping[str, Any] | None = None):
        try:
            manifest_payload = dict(manifest) if manifest is not None else load_model_manifest()
        except BenchmarkManifestError as exc:
            raise ModelRegistryError(str(exc)) from exc

        family_entries = manifest_payload.get("families")
        artifact_entries = manifest_payload.get("artifacts")
        if not isinstance(family_entries, list):
            raise ModelRegistryError("Model manifest must contain a 'families' list.")
        if not isinstance(artifact_entries, list):
            raise ModelRegistryError("Model manifest must contain an 'artifacts' list.")

        self._manifest = manifest_payload
        self._families = self._build_family_index(family_entries)
        self._artifacts = self._build_artifact_index(artifact_entries)

    def list_families(self) -> list[ModelFamilyDescriptor]:
        return list(self._families.values())

    def list_artifacts(self) -> list[ModelArtifactDescriptor]:
        return list(self._artifacts.values())

    def get_artifact_descriptor(self, artifact_id: str) -> ModelArtifactDescriptor:
        try:
            return self._artifacts[artifact_id]
        except KeyError as exc:
            raise ModelArtifactNotFoundError(
                f"Model artifact '{artifact_id}' is not declared in the benchmark manifest."
            ) from exc

    def load_artifact(self, artifact_id: str) -> ModelArtifactHandle:
        artifact = self.get_artifact_descriptor(artifact_id)
        adapter = self._ADAPTERS.get(artifact.family)
        if adapter is None:
            raise ModelRegistryError(f"Unsupported model family adapter: {artifact.family}")
        return adapter.load(artifact)

    def _build_family_index(self, entries: list[Any]) -> dict[str, ModelFamilyDescriptor]:
        families: dict[str, ModelFamilyDescriptor] = {}
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise ModelRegistryError("Model family manifest entries must be objects.")

            family = self._parse_family(entry)
            if family.family in families:
                raise ModelRegistryError(f"Model manifest contains a duplicate family entry: {family.family}")
            families[family.family] = family

        return families

    def _build_artifact_index(self, entries: list[Any]) -> dict[str, ModelArtifactDescriptor]:
        artifacts: dict[str, ModelArtifactDescriptor] = {}
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise ModelRegistryError("Model artifact manifest entries must be objects.")

            artifact = self._parse_artifact(entry)
            if artifact.artifact_id in artifacts:
                raise ModelRegistryError(
                    f"Model manifest contains a duplicate artifact entry: {artifact.artifact_id}"
                )
            artifacts[artifact.artifact_id] = artifact

        return artifacts

    def _parse_family(self, entry: Mapping[str, Any]) -> ModelFamilyDescriptor:
        try:
            family_name = str(entry["family"])
            if family_name not in self._ADAPTERS:
                raise ModelRegistryError(f"Model manifest declares unsupported family '{family_name}'.")

            return ModelFamilyDescriptor(
                family=family_name,
                display_name=str(entry["display_name"]),
                source_repository=str(entry["source_repository"]),
                source_repository_path=resolve_benchmark_path(str(entry["source_repository_path"])),
                weights_root=resolve_benchmark_path(str(entry["weights_root"])),
                supported_datasets=tuple(str(item) for item in entry["supported_datasets"]),
                notes=str(entry["notes"]),
            )
        except KeyError as exc:
            raise ModelRegistryError(f"Model family manifest entry is missing required field: {exc.args[0]}") from exc

    def _parse_artifact(self, entry: Mapping[str, Any]) -> ModelArtifactDescriptor:
        try:
            family_name = str(entry["family"])
            if family_name not in self._ADAPTERS:
                raise ModelRegistryError(
                    f"Model artifact manifest entry declares unsupported family '{family_name}'."
                )

            return ModelArtifactDescriptor(
                artifact_id=str(entry["artifact_id"]),
                family=family_name,
                display_name=str(entry["display_name"]),
                dataset=str(entry["dataset"]),
                status=str(entry["status"]),
                artifact_dir=resolve_benchmark_path(str(entry["artifact_dir"])),
                source_repository=str(entry["source_repository"]),
                source_repository_path=resolve_benchmark_path(str(entry["source_repository_path"])),
                input_shape=tuple(int(value) for value in entry["input_shape"]),
                label_space=tuple(str(value) for value in entry.get("label_space", [])),
                notes=str(entry["notes"]),
            )
        except KeyError as exc:
            raise ModelRegistryError(
                f"Model artifact manifest entry is missing required field: {exc.args[0]}"
            ) from exc
        except ValueError as exc:
            raise ModelRegistryError(f"Model artifact manifest entry has an invalid value: {exc}") from exc
