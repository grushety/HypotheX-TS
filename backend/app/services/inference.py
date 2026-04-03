import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from app.schemas.prediction import PredictionResponse, PredictionScore
from app.services.compatibility import CompatibilityValidator
from app.services.datasets import DatasetRegistry, LoadedDataset
from app.services.models import ModelArtifactHandle, ModelRegistry


class InferenceServiceError(RuntimeError):
    """Base error for inference service failures."""


class SampleSelectionError(InferenceServiceError):
    """Raised when a requested dataset split or sample index is invalid."""


class InferenceAdapterError(InferenceServiceError):
    """Raised when an inference adapter cannot produce a prediction."""


class InferenceAdapter:
    def predict(
        self,
        handle: ModelArtifactHandle,
        sample: np.ndarray,
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        raise NotImplementedError


class PrototypeInferenceAdapter(InferenceAdapter):
    def __init__(self, family: str):
        self.family = family

    def predict(
        self,
        handle: ModelArtifactHandle,
        sample: np.ndarray,
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        metadata = self._read_metadata(handle.metadata_path)
        adapter_name = metadata.get("inference_adapter")
        if adapter_name != "nearest_prototype":
            raise InferenceAdapterError(
                f"Model artifact '{handle.artifact.artifact_id}' does not declare a supported inference adapter."
            )

        prototype_vectors = metadata.get("prototype_vectors")
        if not isinstance(prototype_vectors, list) or not prototype_vectors:
            raise InferenceAdapterError(
                f"Model artifact '{handle.artifact.artifact_id}' is missing prototype_vectors in metadata."
            )

        vector = self._vectorize_sample(sample)
        prototypes = self._normalize_prototypes(
            prototype_vectors,
            target_length=vector.shape[0],
            artifact_id=handle.artifact.artifact_id,
        )

        deltas = prototypes - vector
        scores = tuple(float(-np.sum(deltas * deltas, axis=1)[index]) for index in range(prototypes.shape[0]))
        probabilities = self._softmax(scores)
        return scores, probabilities

    def _vectorize_sample(self, sample: np.ndarray) -> np.ndarray:
        return np.asarray(sample, dtype=np.float64).reshape(-1)

    def _normalize_prototypes(
        self,
        prototype_vectors: list[Any],
        *,
        target_length: int,
        artifact_id: str,
    ) -> np.ndarray:
        normalized_rows: list[np.ndarray] = []
        for prototype_vector in prototype_vectors:
            row = np.asarray(prototype_vector, dtype=np.float64).reshape(-1)
            if row.size == 0:
                raise InferenceAdapterError(
                    f"Model artifact '{artifact_id}' contains an empty prototype vector."
                )
            if row.shape[0] != target_length:
                row = self._resample_vector(row, target_length)
            normalized_rows.append(row)

        prototypes = np.stack(normalized_rows, axis=0)
        if prototypes.ndim != 2:
            raise InferenceAdapterError(
                f"Model artifact '{artifact_id}' prototype_vectors must normalize to a 2D array."
            )
        return prototypes

    def _resample_vector(self, values: np.ndarray, target_length: int) -> np.ndarray:
        if target_length < 1:
            raise InferenceAdapterError("Prediction vectors must have positive length.")
        if values.shape[0] == target_length:
            return values
        if values.shape[0] == 1:
            return np.repeat(values, target_length)

        source_positions = np.arange(values.shape[0], dtype=np.float64)
        target_positions = np.linspace(0, values.shape[0] - 1, num=target_length, dtype=np.float64)
        return np.interp(target_positions, source_positions, values)

    def _read_metadata(self, path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise InferenceAdapterError(f"Model artifact metadata is missing: {path}") from exc
        except json.JSONDecodeError as exc:
            raise InferenceAdapterError(f"Model artifact metadata is not valid JSON: {path}") from exc

    def _softmax(self, scores: tuple[float, ...]) -> tuple[float, ...]:
        max_score = max(scores)
        exps = [math.exp(score - max_score) for score in scores]
        total = sum(exps)
        return tuple(exp_value / total for exp_value in exps)


class PredictionService:
    _ADAPTERS = {
        "fcn": PrototypeInferenceAdapter("fcn"),
        "mlp": PrototypeInferenceAdapter("mlp"),
        "inceptiontime": PrototypeInferenceAdapter("inceptiontime"),
    }

    def __init__(
        self,
        dataset_registry: DatasetRegistry | None = None,
        model_registry: ModelRegistry | None = None,
        compatibility_validator: CompatibilityValidator | None = None,
    ):
        self._dataset_registry = dataset_registry or DatasetRegistry()
        self._model_registry = model_registry or ModelRegistry()
        self._compatibility_validator = compatibility_validator or CompatibilityValidator(
            dataset_registry=self._dataset_registry,
            model_registry=self._model_registry,
        )

    def predict(
        self,
        dataset_name: str,
        artifact_id: str,
        split: str,
        sample_index: int,
    ) -> PredictionResponse:
        compatibility = self._compatibility_validator.validate(dataset_name, artifact_id)
        if not compatibility.is_compatible:
            raise InferenceServiceError(
                "Prediction request is not compatible: " + " ".join(compatibility.messages)
            )

        dataset = self._dataset_registry.load_dataset(dataset_name)
        handle = self._model_registry.load_artifact(artifact_id)
        adapter = self._ADAPTERS.get(handle.artifact.family)
        if adapter is None:
            raise InferenceAdapterError(f"No inference adapter is available for family '{handle.artifact.family}'.")

        sample, true_label = self._select_sample(dataset, split, sample_index)
        try:
            scores, probabilities = adapter.predict(handle, sample)
        except InferenceAdapterError:
            raise
        except Exception as exc:
            raise InferenceAdapterError(
                f"Prediction failed for artifact '{artifact_id}' on dataset '{dataset_name}'."
            ) from exc

        label_space = handle.artifact.label_space
        if len(label_space) != len(scores):
            raise InferenceAdapterError(
                f"Model artifact '{artifact_id}' label space size {len(label_space)} does not match "
                f"prediction score count {len(scores)}."
            )

        score_entries = tuple(
            PredictionScore(
                label=label_space[index],
                score=scores[index],
                probability=probabilities[index],
            )
            for index in range(len(label_space))
        )
        best_index = max(range(len(score_entries)), key=lambda index: score_entries[index].score)

        return PredictionResponse(
            dataset_name=dataset_name,
            artifact_id=artifact_id,
            split=split,
            sample_index=sample_index,
            predicted_label=score_entries[best_index].label,
            true_label=true_label,
            scores=score_entries,
        )

    def _select_sample(
        self,
        dataset: LoadedDataset,
        split: str,
        sample_index: int,
    ) -> tuple[np.ndarray, str | None]:
        if sample_index < 0:
            raise SampleSelectionError(f"Sample index must be non-negative; received {sample_index}.")

        if split == "train":
            series = dataset.train_series
            labels = dataset.train_labels
        elif split == "test":
            series = dataset.test_series
            labels = dataset.test_labels
        else:
            raise SampleSelectionError(f"Split must be 'train' or 'test'; received '{split}'.")

        if sample_index >= series.shape[0]:
            raise SampleSelectionError(
                f"Sample index {sample_index} is out of range for split '{split}' with {series.shape[0]} samples."
            )

        label_index = int(labels[sample_index])
        true_label = None
        if 0 <= label_index < len(dataset.summary.classes):
            true_label = dataset.summary.classes[label_index]

        return series[sample_index], true_label
