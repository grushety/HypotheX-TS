from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from app.core.benchmark_manifest import BenchmarkManifestError, load_dataset_manifest, resolve_benchmark_path
from app.schemas.datasets import DatasetArtifactPaths, DatasetSummary, LoadedDataset


class DatasetRegistryError(RuntimeError):
    """Base error for dataset registry failures."""


class DatasetNotFoundError(DatasetRegistryError):
    """Raised when a requested dataset is not declared in the manifest."""


class DatasetArtifactError(DatasetRegistryError):
    """Raised when dataset artifacts are missing or malformed."""


class DatasetSampleSelectionError(DatasetRegistryError):
    """Raised when a requested split or sample index is invalid."""


class DatasetRegistry:
    def __init__(self, manifest: Mapping[str, Any] | None = None):
        try:
            manifest_payload = dict(manifest) if manifest is not None else load_dataset_manifest()
        except BenchmarkManifestError as exc:
            raise DatasetRegistryError(str(exc)) from exc

        entries = manifest_payload.get("datasets")
        if not isinstance(entries, list):
            raise DatasetRegistryError("Dataset manifest must contain a 'datasets' list.")

        self._manifest = manifest_payload
        self._datasets = self._build_index(entries)

    def list_datasets(self) -> list[DatasetSummary]:
        return list(self._datasets.values())

    def get_dataset_summary(self, dataset_name: str) -> DatasetSummary:
        try:
            return self._datasets[dataset_name]
        except KeyError as exc:
            raise DatasetNotFoundError(f"Dataset '{dataset_name}' is not declared in the benchmark manifest.") from exc

    def load_dataset(self, dataset_name: str) -> LoadedDataset:
        summary = self.get_dataset_summary(dataset_name)

        train_series = self._load_array(summary.artifacts.train_series_path, summary.train_shape, "train series")
        train_labels = self._load_array(
            summary.artifacts.train_labels_path,
            (summary.train_shape[0],),
            "train labels",
        )
        test_series = self._load_array(summary.artifacts.test_series_path, summary.test_shape, "test series")
        test_labels = self._load_array(
            summary.artifacts.test_labels_path,
            (summary.test_shape[0],),
            "test labels",
        )

        return LoadedDataset(
            summary=summary,
            train_series=train_series,
            train_labels=train_labels,
            test_series=test_series,
            test_labels=test_labels,
        )

    def load_sample(self, dataset_name: str, split: str, sample_index: int) -> dict[str, Any]:
        dataset = self.load_dataset(dataset_name)
        series, labels = self._select_split(dataset, split)

        if sample_index < 0:
            raise DatasetSampleSelectionError(f"Sample index must be non-negative; received {sample_index}.")
        if sample_index >= series.shape[0]:
            raise DatasetSampleSelectionError(
                f"Sample index {sample_index} is out of range for split '{split}' with {series.shape[0]} samples."
            )

        label_index = int(labels[sample_index])
        label = None
        if 0 <= label_index < len(dataset.summary.classes):
            label = dataset.summary.classes[label_index]

        values = series[sample_index]
        return {
            "dataset_name": dataset.summary.name,
            "dataset_id": dataset.summary.name,
            "split": split,
            "sample_index": sample_index,
            "task_type": dataset.summary.task_type,
            "series_type": dataset.summary.series_type,
            "channel_count": dataset.summary.n_channels,
            "series_length": int(values.shape[-1]),
            "label": label,
            "values": values.tolist(),
        }

    def _build_index(self, entries: list[Any]) -> dict[str, DatasetSummary]:
        datasets: dict[str, DatasetSummary] = {}
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise DatasetRegistryError("Dataset manifest entries must be objects.")

            summary = self._parse_summary(entry)
            if summary.name in datasets:
                raise DatasetRegistryError(f"Dataset manifest contains a duplicate dataset entry: {summary.name}")
            datasets[summary.name] = summary

        return datasets

    def _parse_summary(self, entry: Mapping[str, Any]) -> DatasetSummary:
        try:
            artifacts = entry["artifacts"]
            return DatasetSummary(
                name=str(entry["name"]),
                status=str(entry["status"]),
                task_type=str(entry["task_type"]),
                series_type=str(entry["series_type"]),
                dataset_dir=resolve_benchmark_path(str(entry["dataset_dir"])),
                raw_dir=resolve_benchmark_path(str(entry["raw_dir"])),
                processed_dir=resolve_benchmark_path(str(entry["processed_dir"])),
                metadata_path=resolve_benchmark_path(str(entry["metadata_path"])),
                summary_path=resolve_benchmark_path(str(entry["summary_path"])),
                source_archive=str(entry["source_archive"]),
                source=str(entry["source"]),
                license_name=entry.get("license"),
                notes=str(entry["notes"]),
                n_channels=int(entry["n_channels"]),
                train_shape=tuple(int(value) for value in entry["train_shape"]),
                test_shape=tuple(int(value) for value in entry["test_shape"]),
                n_classes=int(entry["n_classes"]),
                classes=tuple(str(value) for value in entry["classes"]),
                export_format=str(entry["export_format"]),
                tensor_layout=str(entry["tensor_layout"]),
                artifacts=DatasetArtifactPaths(
                    train_series_path=resolve_benchmark_path(str(artifacts["train_series_path"])),
                    train_labels_path=resolve_benchmark_path(str(artifacts["train_labels_path"])),
                    test_series_path=resolve_benchmark_path(str(artifacts["test_series_path"])),
                    test_labels_path=resolve_benchmark_path(str(artifacts["test_labels_path"])),
                ),
            )
        except KeyError as exc:
            raise DatasetRegistryError(f"Dataset manifest entry is missing required field: {exc.args[0]}") from exc
        except TypeError as exc:
            raise DatasetRegistryError("Dataset manifest entry has an invalid structure.") from exc
        except ValueError as exc:
            raise DatasetRegistryError(f"Dataset manifest entry has an invalid value: {exc}") from exc

    def _load_array(
        self,
        path: Path,
        expected_shape: tuple[int, ...],
        artifact_label: str,
    ) -> np.ndarray:
        if not path.exists():
            raise DatasetArtifactError(f"Dataset {artifact_label} artifact is missing: {path}")

        try:
            array = np.load(path, allow_pickle=False)
        except ValueError as exc:
            raise DatasetArtifactError(f"Dataset {artifact_label} artifact is not a valid NumPy array: {path}") from exc
        except OSError as exc:
            raise DatasetArtifactError(f"Dataset {artifact_label} artifact could not be read: {path}") from exc

        if tuple(array.shape) != expected_shape:
            raise DatasetArtifactError(
                f"Dataset {artifact_label} artifact has shape {tuple(array.shape)}; expected {expected_shape}: {path}"
            )

        return array

    def _select_split(self, dataset: LoadedDataset, split: str) -> tuple[np.ndarray, np.ndarray]:
        if split == "train":
            return dataset.train_series, dataset.train_labels
        if split == "test":
            return dataset.test_series, dataset.test_labels
        raise DatasetSampleSelectionError(f"Split must be 'train' or 'test'; received '{split}'.")
