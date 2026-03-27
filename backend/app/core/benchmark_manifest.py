import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from app.core.paths import (
    BENCHMARK_DATASETS_MANIFEST_PATH,
    BENCHMARK_MODELS_MANIFEST_PATH,
    BENCHMARK_ROOT,
)


class BenchmarkManifestError(RuntimeError):
    """Raised when a benchmark manifest cannot be read safely."""


def resolve_benchmark_path(path_value: str | Path) -> Path:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    return BENCHMARK_ROOT / candidate


def load_dataset_manifest(path: Path = BENCHMARK_DATASETS_MANIFEST_PATH) -> dict[str, Any]:
    return _load_manifest(path)


def load_model_manifest(path: Path = BENCHMARK_MODELS_MANIFEST_PATH) -> dict[str, Any]:
    return _load_manifest(path)


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BenchmarkManifestError(f"Benchmark manifest was not found: {path}") from exc
    except JSONDecodeError as exc:
        raise BenchmarkManifestError(f"Benchmark manifest is not valid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise BenchmarkManifestError(f"Benchmark manifest must decode to an object: {path}")

    return payload
