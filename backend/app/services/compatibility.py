from app.schemas.compatibility import CompatibilityResult
from app.schemas.datasets import DatasetSummary
from app.schemas.models import ModelArtifactDescriptor
from app.services.datasets import DatasetNotFoundError, DatasetRegistry
from app.services.models import ModelArtifactNotFoundError, ModelRegistry


class CompatibilityValidator:
    def __init__(
        self,
        dataset_registry: DatasetRegistry | None = None,
        model_registry: ModelRegistry | None = None,
    ):
        self._dataset_registry = dataset_registry or DatasetRegistry()
        self._model_registry = model_registry or ModelRegistry()
        self._family_index = {
            family.family: family
            for family in self._model_registry.list_families()
        }

    def validate(self, dataset_name: str, artifact_id: str) -> CompatibilityResult:
        messages: list[str] = []

        try:
            dataset = self._dataset_registry.get_dataset_summary(dataset_name)
        except DatasetNotFoundError:
            messages.append(f"Dataset '{dataset_name}' is not declared in the benchmark manifest.")
            return CompatibilityResult(
                dataset_name=dataset_name,
                artifact_id=artifact_id,
                is_compatible=False,
                messages=tuple(messages),
            )

        try:
            artifact = self._model_registry.get_artifact_descriptor(artifact_id)
        except ModelArtifactNotFoundError:
            messages.append(f"Model artifact '{artifact_id}' is not declared in the benchmark manifest.")
            return CompatibilityResult(
                dataset_name=dataset_name,
                artifact_id=artifact_id,
                is_compatible=False,
                messages=tuple(messages),
            )

        return self.validate_descriptors(dataset, artifact)

    def validate_descriptors(
        self,
        dataset: DatasetSummary,
        artifact: ModelArtifactDescriptor,
    ) -> CompatibilityResult:
        messages: list[str] = []
        family = self._family_index.get(artifact.family)
        if family is None:
            messages.append(f"Model family '{artifact.family}' is not supported by the validator.")
            return CompatibilityResult(
                dataset_name=dataset.name,
                artifact_id=artifact.artifact_id,
                is_compatible=False,
                messages=tuple(messages),
            )

        if dataset.name not in family.supported_datasets:
            supported = ", ".join(family.supported_datasets)
            messages.append(
                f"Model family '{artifact.display_name}' does not support dataset '{dataset.name}'. "
                f"Supported datasets: {supported}."
            )

        if artifact.dataset != dataset.name:
            messages.append(
                f"Model artifact '{artifact.artifact_id}' is declared for dataset '{artifact.dataset}', "
                f"not '{dataset.name}'."
            )

        self._check_channel_compatibility(dataset, artifact, messages)
        self._check_series_length_compatibility(dataset, artifact, messages)

        return CompatibilityResult(
            dataset_name=dataset.name,
            artifact_id=artifact.artifact_id,
            is_compatible=not messages,
            messages=tuple(messages),
        )

    def _check_channel_compatibility(
        self,
        dataset: DatasetSummary,
        artifact: ModelArtifactDescriptor,
        messages: list[str],
    ) -> None:
        expected_channels = artifact.input_shape[0]
        if expected_channels == dataset.n_channels:
            return

        if dataset.is_univariate:
            messages.append(
                f"Dataset '{dataset.name}' is univariate with 1 channel, but model artifact "
                f"'{artifact.artifact_id}' expects {expected_channels} channels."
            )
            return

        messages.append(
            f"Dataset '{dataset.name}' is multivariate with {dataset.n_channels} channels, but model artifact "
            f"'{artifact.artifact_id}' expects {expected_channels} channels."
        )

    def _check_series_length_compatibility(
        self,
        dataset: DatasetSummary,
        artifact: ModelArtifactDescriptor,
        messages: list[str],
    ) -> None:
        expected_length = artifact.input_shape[1]
        actual_length = dataset.train_shape[2]
        if expected_length != actual_length:
            messages.append(
                f"Dataset '{dataset.name}' series length is {actual_length}, but model artifact "
                f"'{artifact.artifact_id}' expects length {expected_length}."
            )
