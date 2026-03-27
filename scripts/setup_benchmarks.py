#!/usr/bin/env python3
"""Prepare a local HypotheX-TS benchmark workspace.

This script downloads selected UCR/UEA benchmark datasets, exports them into
normalized NumPy arrays for app use, and clones the reference model
repositories needed for later training experiments.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import requests

try:
    import aeon  # noqa: F401

    AEON_AVAILABLE = True
except ImportError:
    AEON_AVAILABLE = False


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = PROJECT_ROOT / "benchmarks"
EXPORT_FORMATS = {"npy"}


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    archive_key: str
    description_url: str
    source: str
    univariate: bool
    n_channels: int
    license_name: str | None
    notes: str


ARCHIVE_SOURCES = {
    "univariate_ts": {
        "url": "https://www.timeseriesclassification.com/aeon-toolkit/Archives/Univariate2018_ts.zip",
        "download_name": "Univariate2018_ts.zip",
        "extract_dir_name": "univariate_ts",
        "description": "Official UCR/UEA univariate aeon-format archive",
    },
    "multivariate_ts": {
        "url": "https://www.timeseriesclassification.com/aeon-toolkit/Archives/Multivariate2018_ts.zip",
        "download_name": "Multivariate2018_ts.zip",
        "extract_dir_name": "multivariate_ts",
        "description": "Official UCR/UEA multivariate aeon-format archive",
    },
}

DATASETS: dict[str, DatasetConfig] = {
    "GunPoint": DatasetConfig(
        name="GunPoint",
        archive_key="univariate_ts",
        description_url="https://www.timeseriesclassification.com/description.php?Dataset=GunPoint",
        source="UCR/UEA Time Series Classification Archive",
        univariate=True,
        n_channels=1,
        license_name=None,
        notes="Canonical source is the Time Series Classification archive description page.",
    ),
    "ECG200": DatasetConfig(
        name="ECG200",
        archive_key="univariate_ts",
        description_url="https://www.timeseriesclassification.com/description.php?Dataset=ECG200",
        source="UCR/UEA Time Series Classification Archive",
        univariate=True,
        n_channels=1,
        license_name=None,
        notes="Canonical source is the Time Series Classification archive description page.",
    ),
    "Wafer": DatasetConfig(
        name="Wafer",
        archive_key="univariate_ts",
        description_url="https://www.timeseriesclassification.com/description.php?Dataset=Wafer",
        source="UCR/UEA Time Series Classification Archive",
        univariate=True,
        n_channels=1,
        license_name=None,
        notes="Canonical source is the Time Series Classification archive description page.",
    ),
    "BasicMotions": DatasetConfig(
        name="BasicMotions",
        archive_key="multivariate_ts",
        description_url="https://www.timeseriesclassification.com/description.php?Dataset=BasicMotions",
        source="UEA Multivariate Time Series Classification Archive",
        univariate=False,
        n_channels=6,
        license_name=None,
        notes="Smartwatch accelerometer and gyroscope benchmark from the UEA archive.",
    ),
}

MODEL_REPOS = {
    "dl-4-tsc": {
        "url": "https://github.com/hfawaz/dl-4-tsc.git",
        "destination": "dl-4-tsc",
        "models": ["fcn", "mlp"],
        "license": "GPL-3.0",
    },
    "InceptionTime": {
        "url": "https://github.com/hfawaz/InceptionTime.git",
        "destination": "InceptionTime",
        "models": ["inceptiontime"],
        "license": "GPL-3.0",
    },
}

MODEL_FAMILIES = {
    "fcn": {
        "display_name": "FCN",
        "repo_key": "dl-4-tsc",
        "weights_subdir": "fcn",
        "notes": "Place trained FCN artifacts under models/weights/fcn/<DATASET>/.",
    },
    "mlp": {
        "display_name": "MLP",
        "repo_key": "dl-4-tsc",
        "weights_subdir": "mlp",
        "notes": "Place trained MLP artifacts under models/weights/mlp/<DATASET>/.",
    },
    "inceptiontime": {
        "display_name": "InceptionTime",
        "repo_key": "InceptionTime",
        "weights_subdir": "inceptiontime",
        "notes": "Place trained InceptionTime artifacts under models/weights/inceptiontime/<DATASET>/.",
    },
}


class SetupError(RuntimeError):
    """Raised when setup cannot continue safely."""


def log(message: str) -> None:
    print(f"[setup] {message}")


def warn(message: str) -> None:
    print(f"[warn] {message}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and organize benchmark datasets and model repos for HypotheX-TS."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help=f"Benchmark root directory. Default: {DEFAULT_ROOT}",
    )
    parser.add_argument(
        "--datasets",
        default="all",
        help="Datasets to set up: 'all' or a comma-separated list (e.g. GunPoint,ECG200).",
    )
    parser.add_argument(
        "--skip-model-repos",
        action="store_true",
        help="Skip cloning the model repositories.",
    )
    parser.add_argument(
        "--force-redownload",
        action="store_true",
        help="Redownload archives and rebuild dataset exports even if they already exist.",
    )
    parser.add_argument(
        "--export-format",
        default="npy",
        choices=sorted(EXPORT_FORMATS),
        help="Processed export format. Only 'npy' is currently supported.",
    )
    return parser.parse_args()


def resolve_datasets(selection: str) -> list[DatasetConfig]:
    if selection.strip().lower() == "all":
        return [DATASETS[name] for name in DATASETS]

    requested = [item.strip() for item in selection.split(",") if item.strip()]
    if not requested:
        raise SetupError("No datasets selected.")

    unknown = [name for name in requested if name not in DATASETS]
    if unknown:
        available = ", ".join(DATASETS)
        raise SetupError(f"Unknown dataset(s): {', '.join(unknown)}. Available: {available}")

    return [DATASETS[name] for name in requested]


def ensure_structure(root: Path) -> dict[str, Path]:
    paths = {
        "root": root,
        "raw_archives": root / "raw" / "archives" / "ucr_uea",
        "raw_downloads": root / "raw" / "downloads",
        "datasets": root / "datasets",
        "repos": root / "models" / "repos",
        "weights": root / "models" / "weights",
        "configs": root / "models" / "configs",
        "manifests": root / "manifests",
    }

    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)

    for model_name in ("fcn", "mlp", "inceptiontime"):
        (paths["weights"] / model_name).mkdir(parents=True, exist_ok=True)

    return paths


def download_file(url: str, destination: Path, force: bool, timeout: int = 120) -> dict[str, Any]:
    if destination.exists() and not force:
        log(f"Using existing download: {destination}")
        return {"path": str(destination), "downloaded": False, "url": url}

    destination.parent.mkdir(parents=True, exist_ok=True)
    log(f"Downloading {url}")

    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, dir=str(destination.parent)) as tmp:
            tmp_path = Path(tmp.name)
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    tmp.write(chunk)

    tmp_path.replace(destination)
    return {"path": str(destination), "downloaded": True, "url": url}


def extract_zip(zip_path: Path, destination: Path, force: bool) -> dict[str, Any]:
    marker = destination / ".extracted.ok"
    if destination.exists() and marker.exists() and not force:
        log(f"Using existing extracted archive: {destination}")
        return {"path": str(destination), "extracted": False}

    if destination.exists() and force:
        shutil.rmtree(destination)

    destination.mkdir(parents=True, exist_ok=True)
    log(f"Extracting {zip_path.name} -> {destination}")
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(destination)
    marker.write_text(
        json.dumps(
            {
                "source_zip": str(zip_path),
                "extracted_at": utc_now(),
            },
            indent=2,
        )
        + os.linesep,
        encoding="utf-8",
    )
    return {"path": str(destination), "extracted": True}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_ts_file(ts_path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    metadata: dict[str, Any] = {}
    labels: list[str] = []
    records: list[list[np.ndarray]] = []
    data_started = False

    with ts_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if not data_started:
                lower = line.lower()
                if lower.startswith("@data"):
                    data_started = True
                    continue

                if lower.startswith("@problemname"):
                    metadata["problem_name"] = line.split(maxsplit=1)[1].strip()
                elif lower.startswith("@timestamps"):
                    metadata["timestamps"] = line.split(maxsplit=1)[1].strip().lower() == "true"
                elif lower.startswith("@univariate"):
                    metadata["univariate"] = line.split(maxsplit=1)[1].strip().lower() == "true"
                elif lower.startswith("@classlabel"):
                    parts = line.split()
                    metadata["class_label"] = parts[1].lower() == "true"
                    metadata["class_values"] = parts[2:] if len(parts) > 2 else []
                elif lower.startswith("@targetlabel"):
                    metadata["target_label"] = line.split(maxsplit=1)[1].strip().lower() == "true"
                continue

            parts = [part.strip() for part in line.split(":")]
            if metadata.get("class_label", True):
                label = parts[-1]
                dimension_parts = parts[:-1]
            else:
                label = ""
                dimension_parts = parts

            case_dims: list[np.ndarray] = []
            for dim_text in dimension_parts:
                values = [value.strip() for value in dim_text.split(",") if value.strip()]
                if not values:
                    case_dims.append(np.array([], dtype=np.float32))
                    continue
                dim_values = [
                    np.nan if value == "?" else float(value)
                    for value in values
                ]
                case_dims.append(np.asarray(dim_values, dtype=np.float32))

            if not case_dims:
                raise SetupError(f"No dimensions parsed from {ts_path}")

            records.append(case_dims)
            labels.append(label)

    if not data_started:
        raise SetupError(f"{ts_path} is missing an @data section.")
    if not records:
        raise SetupError(f"{ts_path} did not contain any records.")

    n_dims = len(records[0])
    lengths = {len(dim) for case in records for dim in case}
    if len(lengths) != 1:
        raise SetupError(
            f"{ts_path} contains variable-length series; this script expects equal length datasets."
        )

    series_length = lengths.pop()
    for case in records:
        if len(case) != n_dims:
            raise SetupError(f"Inconsistent channel count in {ts_path}")

    array = np.stack([np.stack(case, axis=0) for case in records], axis=0).astype(np.float32)
    label_array = np.asarray(labels, dtype=object)
    metadata.update(
        {
            "n_cases": int(array.shape[0]),
            "n_channels": int(array.shape[1]),
            "series_length": int(series_length),
        }
    )
    return array, label_array, metadata


def normalize_with_train_stats(
    x_train: np.ndarray, x_test: np.ndarray
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    mean = x_train.mean(axis=(0, 2), keepdims=True)
    std = x_train.std(axis=(0, 2), keepdims=True)
    std = np.where(std == 0, 1.0, std)

    x_train_norm = ((x_train - mean) / std).astype(np.float32)
    x_test_norm = ((x_test - mean) / std).astype(np.float32)

    stats = {
        "mean": mean.reshape(-1).tolist(),
        "std": std.reshape(-1).tolist(),
        "applied_to": "per-channel train-set z-normalization",
    }
    return x_train_norm, x_test_norm, stats


def encode_labels(y_train: np.ndarray, y_test: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    ordered_labels = []
    seen: set[str] = set()
    for item in np.concatenate((y_train, y_test), axis=0):
        label = str(item)
        if label not in seen:
            seen.add(label)
            ordered_labels.append(label)

    mapping = {label: index for index, label in enumerate(ordered_labels)}
    train_encoded = np.asarray([mapping[str(item)] for item in y_train], dtype=np.int64)
    test_encoded = np.asarray([mapping[str(item)] for item in y_test], dtype=np.int64)
    return train_encoded, test_encoded, mapping


def copy_dataset_raw_files(dataset_name: str, archive_dataset_dir: Path, dataset_raw_dir: Path) -> list[str]:
    dataset_raw_dir.mkdir(parents=True, exist_ok=True)
    copied_files: list[str] = []

    for file_path in sorted(archive_dataset_dir.iterdir()):
        if file_path.is_file():
            destination = dataset_raw_dir / file_path.name
            shutil.copy2(file_path, destination)
            copied_files.append(destination.name)

    return copied_files


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + os.linesep, encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_to_root(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def root_label(root: Path) -> str:
    try:
        return root.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(root)


def dataset_expected_files(dataset_dir: Path) -> list[Path]:
    processed = dataset_dir / "processed"
    return [
        dataset_dir / "metadata.json",
        processed / "X_train.npy",
        processed / "y_train.npy",
        processed / "X_test.npy",
        processed / "y_test.npy",
        processed / "summary.json",
    ]


def resolve_archive_dataset_dir(archive_root: Path, dataset_name: str) -> Path:
    direct = archive_root / dataset_name
    if direct.exists():
        return direct

    nested_candidates = [child for child in archive_root.iterdir() if child.is_dir()]
    for candidate in nested_candidates:
        nested = candidate / dataset_name
        if nested.exists():
            return nested

    return direct


def process_dataset(
    config: DatasetConfig,
    paths: dict[str, Path],
    archive_roots: dict[str, Path],
    force: bool,
) -> dict[str, Any]:
    dataset_dir = paths["datasets"] / config.name
    dataset_raw_dir = dataset_dir / "raw"
    dataset_processed_dir = dataset_dir / "processed"
    dataset_metadata_path = dataset_dir / "metadata.json"
    expected_files = dataset_expected_files(dataset_dir)

    dataset_dir.mkdir(parents=True, exist_ok=True)
    dataset_raw_dir.mkdir(parents=True, exist_ok=True)
    dataset_processed_dir.mkdir(parents=True, exist_ok=True)

    archive_dataset_dir = resolve_archive_dataset_dir(archive_roots[config.archive_key], config.name)
    if not archive_dataset_dir.exists():
        raise SetupError(
            f"Expected extracted dataset folder was not found for {config.name}: {archive_dataset_dir}"
        )

    if force:
        for path in expected_files:
            if path.exists():
                path.unlink()

    if all(path.exists() for path in expected_files):
        log(f"Dataset already prepared: {config.name}")
        summary = json.loads((dataset_processed_dir / "summary.json").read_text(encoding="utf-8"))
        return {
            "name": config.name,
            "status": "skipped",
            "dataset_dir": str(dataset_dir),
            "processed_dir": str(dataset_processed_dir),
            "summary": summary,
            "metadata_path": str(dataset_metadata_path),
        }

    copied_raw_files = copy_dataset_raw_files(config.name, archive_dataset_dir, dataset_raw_dir)
    train_path = dataset_raw_dir / f"{config.name}_TRAIN.ts"
    test_path = dataset_raw_dir / f"{config.name}_TEST.ts"
    if not train_path.exists() or not test_path.exists():
        raise SetupError(
            f"Expected train/test files missing for {config.name}: {train_path.name}, {test_path.name}"
        )

    x_train_raw, y_train_raw, train_meta = parse_ts_file(train_path)
    x_test_raw, y_test_raw, test_meta = parse_ts_file(test_path)

    if x_train_raw.shape[1] != x_test_raw.shape[1]:
        raise SetupError(f"Mismatched channel count between train/test for {config.name}")
    if x_train_raw.shape[2] != x_test_raw.shape[2]:
        raise SetupError(f"Mismatched series length between train/test for {config.name}")

    y_train, y_test, label_mapping = encode_labels(y_train_raw, y_test_raw)
    x_train, x_test, normalization_stats = normalize_with_train_stats(x_train_raw, x_test_raw)

    np.save(dataset_processed_dir / "X_train.npy", x_train)
    np.save(dataset_processed_dir / "y_train.npy", y_train)
    np.save(dataset_processed_dir / "X_test.npy", x_test)
    np.save(dataset_processed_dir / "y_test.npy", y_test)

    summary = {
        "name": config.name,
        "export_format": "npy",
        "tensor_layout": "n_samples x n_channels x series_length",
        "raw_train_shape": list(map(int, x_train_raw.shape)),
        "raw_test_shape": list(map(int, x_test_raw.shape)),
        "train_shape": list(map(int, x_train.shape)),
        "test_shape": list(map(int, x_test.shape)),
        "n_classes": int(len(label_mapping)),
        "classes": list(label_mapping.keys()),
        "label_mapping": label_mapping,
        "normalization": normalization_stats,
        "raw_files": copied_raw_files,
    }
    write_json(dataset_processed_dir / "summary.json", summary)

    metadata = {
        "name": config.name,
        "task_type": "classification",
        "univariate": config.univariate,
        "n_channels": int(train_meta["n_channels"]),
        "train_split_present": True,
        "test_split_present": True,
        "source": config.description_url,
        "license": config.license_name,
        "notes": config.notes,
    }
    write_json(dataset_metadata_path, metadata)

    log(
        f"Prepared {config.name}: train {tuple(x_train.shape)}, test {tuple(x_test.shape)}, "
        f"classes={len(label_mapping)}"
    )
    return {
        "name": config.name,
        "status": "prepared",
        "dataset_dir": str(dataset_dir),
        "processed_dir": str(dataset_processed_dir),
        "summary": summary,
        "metadata_path": str(dataset_metadata_path),
        "archive_source": config.archive_key,
        "train_meta": train_meta,
        "test_meta": test_meta,
    }


def ensure_repo_cloned(destination: Path, url: str) -> dict[str, Any]:
    if destination.exists() and (destination / ".git").exists():
        log(f"Repository already present: {destination.name}")
        return {"name": destination.name, "status": "skipped", "path": str(destination), "url": url}

    if destination.exists() and not (destination / ".git").exists():
        raise SetupError(f"Destination exists but is not a git repo: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    log(f"Cloning {url} -> {destination}")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", url, str(destination)],
            check=True,
        )
    except FileNotFoundError as exc:
        raise SetupError("git is not installed or not available on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise SetupError(f"Failed to clone repository {url}") from exc

    return {"name": destination.name, "status": "cloned", "path": str(destination), "url": url}


def build_sources_manifest(selected_datasets: list[DatasetConfig], include_repos: bool) -> dict[str, Any]:
    used_archive_keys = sorted({dataset.archive_key for dataset in selected_datasets})
    archive_entries = [
        {
            "name": key,
            "kind": "dataset_archive",
            "url": ARCHIVE_SOURCES[key]["url"],
            "description": ARCHIVE_SOURCES[key]["description"],
        }
        for key in used_archive_keys
    ]

    dataset_entries = [
        {
            "name": dataset.name,
            "kind": "dataset_description",
            "url": dataset.description_url,
            "archive_key": dataset.archive_key,
            "source": dataset.source,
        }
        for dataset in selected_datasets
    ]

    repo_entries: list[dict[str, Any]] = []
    if include_repos:
        for name, repo in MODEL_REPOS.items():
            repo_entries.append(
                {
                    "name": name,
                    "kind": "model_repository",
                    "url": repo["url"],
                    "license": repo["license"],
                    "models": repo["models"],
                }
            )

    return {
        "generated_at": utc_now(),
        "archives": archive_entries,
        "datasets": dataset_entries,
        "models": repo_entries,
        "notes": [
            "Timeseriesclassification.com description pages are recorded as canonical dataset pages.",
            "Official aeon-format archive ZIPs are recorded as the stable download sources.",
        ],
    }


def build_datasets_manifest(root: Path, results: list[dict[str, Any]]) -> dict[str, Any]:
    datasets = []
    for item in results:
        dataset_config = DATASETS[item["name"]]
        dataset_dir = Path(item["dataset_dir"])
        processed_dir = Path(item["processed_dir"])
        metadata_path = Path(item["metadata_path"])
        summary = read_json(processed_dir / "summary.json")
        metadata = read_json(metadata_path)
        datasets.append(
            {
                "name": item["name"],
                "status": item["status"],
                "task_type": metadata["task_type"],
                "series_type": "univariate" if metadata["univariate"] else "multivariate",
                "dataset_dir": relative_to_root(dataset_dir, root),
                "raw_dir": relative_to_root(dataset_dir / "raw", root),
                "processed_dir": relative_to_root(processed_dir, root),
                "metadata_path": relative_to_root(metadata_path, root),
                "summary_path": relative_to_root(processed_dir / "summary.json", root),
                "source_archive": dataset_config.archive_key,
                "source": metadata["source"],
                "license": metadata["license"],
                "notes": metadata["notes"],
                "n_channels": metadata["n_channels"],
                "train_shape": summary["train_shape"],
                "test_shape": summary["test_shape"],
                "n_classes": summary["n_classes"],
                "classes": summary["classes"],
                "export_format": summary["export_format"],
                "tensor_layout": summary["tensor_layout"],
                "artifacts": {
                    "train_series_path": relative_to_root(processed_dir / "X_train.npy", root),
                    "train_labels_path": relative_to_root(processed_dir / "y_train.npy", root),
                    "test_series_path": relative_to_root(processed_dir / "X_test.npy", root),
                    "test_labels_path": relative_to_root(processed_dir / "y_test.npy", root),
                },
            }
        )

    return {
        "schema_version": "1.0",
        "generated_at": utc_now(),
        "benchmark_root": root_label(root),
        "paths": {
            "datasets_root": "datasets",
            "raw_root": "raw",
            "manifests_root": "manifests",
            "model_repos_root": "models/repos",
            "model_weights_root": "models/weights",
        },
        "supported_datasets": [dataset.name for dataset in DATASETS.values()],
        "datasets": datasets,
    }


def build_models_manifest(root: Path, dataset_results: list[dict[str, Any]]) -> dict[str, Any]:
    dataset_summaries: dict[str, dict[str, Any]] = {}
    for item in dataset_results:
        processed_dir = Path(item["processed_dir"])
        dataset_summaries[item["name"]] = read_json(processed_dir / "summary.json")

    families = []
    artifacts = []
    for family_name, family in MODEL_FAMILIES.items():
        repo = MODEL_REPOS[family["repo_key"]]
        families.append(
            {
                "family": family_name,
                "display_name": family["display_name"],
                "source_repository": family["repo_key"],
                "source_repository_path": relative_to_root(
                    root / "models" / "repos" / repo["destination"],
                    root,
                ),
                "weights_root": relative_to_root(
                    root / "models" / "weights" / family["weights_subdir"],
                    root,
                ),
                "supported_datasets": [dataset.name for dataset in DATASETS.values()],
                "notes": family["notes"],
            }
        )

        for dataset_name, summary in dataset_summaries.items():
            artifacts.append(
                {
                    "artifact_id": f"{family_name}-{dataset_name.lower()}",
                    "family": family_name,
                    "display_name": family["display_name"],
                    "dataset": dataset_name,
                    "status": "expected",
                    "artifact_dir": relative_to_root(
                        root / "models" / "weights" / family["weights_subdir"] / dataset_name,
                        root,
                    ),
                    "source_repository": family["repo_key"],
                    "source_repository_path": relative_to_root(
                        root / "models" / "repos" / repo["destination"],
                        root,
                    ),
                    "input_shape": [
                        int(summary["train_shape"][1]),
                        int(summary["train_shape"][2]),
                    ],
                    "label_space": summary["classes"],
                    "notes": (
                        f"Expected placement for a trained {family['display_name']} artifact "
                        f"compatible with {dataset_name}."
                    ),
                }
            )

    return {
        "schema_version": "1.0",
        "generated_at": utc_now(),
        "benchmark_root": root_label(root),
        "paths": {
            "model_repos_root": "models/repos",
            "model_weights_root": "models/weights",
        },
        "supported_model_families": [family["display_name"] for family in MODEL_FAMILIES.values()],
        "families": families,
        "artifacts": artifacts,
    }


def write_benchmarks_readme(root: Path, selected_datasets: list[DatasetConfig], include_repos: bool) -> None:
    dataset_names = ", ".join(dataset.name for dataset in selected_datasets)
    repo_text = "included" if include_repos else "skipped by request"
    content = f"""# HypotheX-TS Benchmarks

This directory stores benchmark datasets, raw downloads, prepared NumPy exports, and reference model codebases for later experiments.

## Structure

- `raw/downloads/`: original downloaded archive files.
- `raw/archives/ucr_uea/`: extracted canonical UCR/UEA archive contents.
- `datasets/<DATASET>/raw/`: dataset-specific raw train/test files copied from the archive.
- `datasets/<DATASET>/processed/`: normalized `.npy` exports for app loading.
- `models/repos/`: cloned reference repositories.
- `models/weights/<FAMILY>/<DATASET>/`: canonical location for trained model artifacts.
- `models/configs/`: reserved location for benchmark config files.
- `manifests/datasets.json`: canonical dataset manifest with repo-relative artifact paths.
- `manifests/models.json`: canonical model-family and artifact-location manifest.
- `manifests/`: generated manifest directory and setup report.

## Included In This Workspace

- Datasets: {dataset_names}
- Model repos: {repo_text}
- Supported model families: FCN, MLP, InceptionTime

## Next Steps

1. Run `python scripts/setup_benchmarks.py --datasets all` to populate this workspace.
2. Inspect `manifests/datasets.json`, `manifests/models.json`, and `manifests/setup_report.json`.
3. Use the exported arrays in `datasets/<DATASET>/processed/` for app integration or later training jobs.
4. Place trained weights under `models/weights/<FAMILY>/<DATASET>/` so backend loaders can resolve them through the manifest contract.
5. Add benchmark-specific training configs under `models/configs/` when training is introduced.
"""
    (root / "README.md").write_text(content, encoding="utf-8")


def build_setup_report(
    root: Path,
    dataset_results: list[dict[str, Any]],
    repo_results: list[dict[str, Any]],
    warnings: list[str],
    args: argparse.Namespace,
) -> dict[str, Any]:
    return {
        "generated_at": utc_now(),
        "root": str(root),
        "arguments": {
            "root": str(args.root),
            "datasets": args.datasets,
            "skip_model_repos": bool(args.skip_model_repos),
            "force_redownload": bool(args.force_redownload),
            "export_format": args.export_format,
        },
        "aeon_available": AEON_AVAILABLE,
        "dataset_results": dataset_results,
        "repo_results": repo_results,
        "warnings": warnings,
    }


def main() -> int:
    args = parse_args()

    try:
        selected_datasets = resolve_datasets(args.datasets)
    except SetupError as exc:
        warn(str(exc))
        return 2

    if args.export_format not in EXPORT_FORMATS:
        warn(f"Unsupported export format: {args.export_format}")
        return 2

    root = args.root.resolve()
    paths = ensure_structure(root)
    warnings_list: list[str] = []

    if AEON_AVAILABLE:
        log("aeon is installed; canonical archive downloads will still be preserved for raw reproducibility.")
    else:
        message = (
            "aeon is not installed. Falling back to direct official archive downloads and built-in TS parsing. "
            "Install aeon later with 'pip install aeon' if you want the toolkit available for manual inspection."
        )
        log(message)
        warnings_list.append(message)

    archive_roots: dict[str, Path] = {}
    required_archive_keys = sorted({dataset.archive_key for dataset in selected_datasets})
    setup_actions: dict[str, Any] = {"downloads": [], "extractions": []}

    try:
        for archive_key in required_archive_keys:
            archive_info = ARCHIVE_SOURCES[archive_key]
            zip_path = paths["raw_downloads"] / archive_info["download_name"]
            download_result = download_file(
                archive_info["url"],
                zip_path,
                force=args.force_redownload,
            )
            extract_root = paths["raw_archives"] / archive_info["extract_dir_name"]
            extract_result = extract_zip(zip_path, extract_root, force=args.force_redownload)
            archive_roots[archive_key] = extract_root
            setup_actions["downloads"].append(download_result)
            setup_actions["extractions"].append(extract_result)
    except (requests.RequestException, zipfile.BadZipFile, OSError, SetupError) as exc:
        warn(f"Archive setup failed: {exc}")
        return 1

    dataset_results: list[dict[str, Any]] = []
    try:
        for dataset in selected_datasets:
            dataset_results.append(
                process_dataset(
                    config=dataset,
                    paths=paths,
                    archive_roots=archive_roots,
                    force=args.force_redownload,
                )
            )
    except (OSError, ValueError, SetupError) as exc:
        warn(f"Dataset setup failed: {exc}")
        return 1

    repo_results: list[dict[str, Any]] = []
    if not args.skip_model_repos:
        for _, repo in MODEL_REPOS.items():
            destination = paths["repos"] / repo["destination"]
            try:
                repo_results.append(ensure_repo_cloned(destination, repo["url"]))
            except SetupError as exc:
                warning = str(exc)
                warnings_list.append(warning)
                warn(warning)
    else:
        log("Skipping model repository cloning.")

    sources_manifest = build_sources_manifest(selected_datasets, include_repos=not args.skip_model_repos)
    datasets_manifest = build_datasets_manifest(root, dataset_results)
    models_manifest = build_models_manifest(root, dataset_results)
    setup_report = build_setup_report(root, dataset_results, repo_results, warnings_list, args)
    setup_report["actions"] = setup_actions

    write_json(paths["manifests"] / "sources.json", sources_manifest)
    write_json(paths["manifests"] / "datasets.json", datasets_manifest)
    write_json(paths["manifests"] / "models.json", models_manifest)
    write_json(paths["manifests"] / "setup_report.json", setup_report)
    write_benchmarks_readme(root, selected_datasets, include_repos=not args.skip_model_repos)

    log("Setup complete.")
    log(f"Datasets prepared: {len(dataset_results)}")
    for result in dataset_results:
        summary = result["summary"]
        log(
            f"  - {result['name']}: train={tuple(summary['train_shape'])}, "
            f"test={tuple(summary['test_shape'])}, classes={summary['n_classes']}"
        )

    if args.skip_model_repos:
        log("Model repos: skipped")
    else:
        log(f"Model repos processed: {len(repo_results)}")
        for result in repo_results:
            log(f"  - {result['name']}: {result['status']}")

    if warnings_list:
        log(f"Warnings recorded: {len(warnings_list)}")
        for item in warnings_list:
            warn(item)

    log(f"Artifacts written under: {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
