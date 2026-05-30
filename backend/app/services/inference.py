import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from app.schemas.prediction import (
    AdHocPredictionResponse,
    PredictionResponse,
    PredictionScore,
    PredictionTransform,
)
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
        adapter = self._resolve_adapter(handle)

        sample, true_label = self._select_sample(dataset, split, sample_index)
        model_input, transforms = self._transform_input(sample)
        score_entries, best_index = self._score(
            adapter, handle, model_input, dataset_name=dataset_name
        )

        return PredictionResponse(
            dataset_name=dataset_name,
            artifact_id=artifact_id,
            split=split,
            sample_index=sample_index,
            predicted_label=score_entries[best_index].label,
            true_label=true_label,
            scores=score_entries,
            transforms=transforms,
            model_input_length=int(model_input.shape[0]),
        )

    def predict_values(
        self,
        artifact_id: str,
        values: list[float] | np.ndarray,
    ) -> AdHocPredictionResponse:
        """Score an arbitrary value vector (e.g. an edited / counterfactual series).

        Skips dataset loading and compatibility validation — the caller has produced
        the values themselves and only needs the model artifact applied to them.
        """
        if values is None:
            raise SampleSelectionError("Prediction values vector is required.")

        sample = np.asarray(values)
        if sample.size == 0:
            raise SampleSelectionError("Prediction values vector must be non-empty.")

        model_input, transforms = self._transform_input(sample)
        handle = self._model_registry.load_artifact(artifact_id)
        adapter = self._resolve_adapter(handle)
        score_entries, best_index = self._score(
            adapter, handle, model_input, dataset_name=None
        )

        return AdHocPredictionResponse(
            artifact_id=artifact_id,
            predicted_label=score_entries[best_index].label,
            scores=score_entries,
            transforms=transforms,
            model_input_length=int(model_input.shape[0]),
        )

    @staticmethod
    def _transform_input(sample: np.ndarray) -> tuple[np.ndarray, tuple[PredictionTransform, ...]]:
        """Apply + describe the deterministic input-side preprocessing.

        This is the single source of truth for what the model sees on the
        **input side**. The returned vector is the exact 1-D float64 array
        passed to the adapter; the returned tuple lists every transform
        applied to get there. The adapter's own ``_vectorize_sample``
        becomes idempotent on the result, so this list IS the full
        input-side preprocessing path.

        Prototype-side resampling (``PrototypeInferenceAdapter._resample_vector``)
        is intentionally NOT included here — that operation adapts each
        prototype to the user's input length and does not modify the user's
        series. The "Model sees this" fidelity strip describes what happens
        to the user's edited values; the prototype side is a model-internal
        adapter detail.
        """
        arr = np.asarray(sample)
        transforms: list[PredictionTransform] = []

        if arr.dtype != np.float64:
            before_dtype = str(arr.dtype)
            transforms.append(
                PredictionTransform(
                    name="cast_float64",
                    params={"from_dtype": before_dtype, "to_dtype": "float64"},
                    before_shape=tuple(int(dim) for dim in arr.shape),
                    after_shape=tuple(int(dim) for dim in arr.shape),
                )
            )
            arr = arr.astype(np.float64)

        if arr.ndim != 1:
            before_shape = tuple(int(dim) for dim in arr.shape)
            arr = arr.reshape(-1)
            transforms.append(
                PredictionTransform(
                    name="flatten",
                    params={"order": "C"},
                    before_shape=before_shape,
                    after_shape=(int(arr.shape[0]),),
                )
            )

        return arr, tuple(transforms)

    def _resolve_adapter(self, handle: ModelArtifactHandle) -> InferenceAdapter:
        adapter = self._ADAPTERS.get(handle.artifact.family)
        if adapter is None:
            raise InferenceAdapterError(
                f"No inference adapter is available for family '{handle.artifact.family}'."
            )
        return adapter

    def _score(
        self,
        adapter: InferenceAdapter,
        handle: ModelArtifactHandle,
        sample: np.ndarray,
        *,
        dataset_name: str | None,
    ) -> tuple[tuple[PredictionScore, ...], int]:
        artifact_id = handle.artifact.artifact_id
        try:
            scores, probabilities = adapter.predict(handle, sample)
        except InferenceAdapterError:
            raise
        except Exception as exc:
            context = f" on dataset '{dataset_name}'" if dataset_name else ""
            raise InferenceAdapterError(
                f"Prediction failed for artifact '{artifact_id}'{context}."
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
        return score_entries, best_index

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
