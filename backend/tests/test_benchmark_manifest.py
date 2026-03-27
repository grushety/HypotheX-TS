from pathlib import Path

from app.config import Config
from app.core.benchmark_manifest import (
    load_dataset_manifest,
    load_model_manifest,
    resolve_benchmark_path,
)
from app.core.paths import (
    BENCHMARK_DATASETS_DIR,
    BENCHMARK_DATASETS_MANIFEST_PATH,
    BENCHMARK_MANIFESTS_DIR,
    BENCHMARK_MODEL_REPOS_DIR,
    BENCHMARK_MODEL_WEIGHTS_DIR,
    BENCHMARK_MODELS_MANIFEST_PATH,
    BENCHMARK_RAW_DIR,
    BENCHMARK_ROOT,
)


def test_benchmark_path_contract_is_centralized():
    assert BENCHMARK_DATASETS_DIR == BENCHMARK_ROOT / "datasets"
    assert BENCHMARK_RAW_DIR == BENCHMARK_ROOT / "raw"
    assert BENCHMARK_MODEL_REPOS_DIR == BENCHMARK_ROOT / "models" / "repos"
    assert BENCHMARK_MODEL_WEIGHTS_DIR == BENCHMARK_ROOT / "models" / "weights"
    assert BENCHMARK_MANIFESTS_DIR == BENCHMARK_ROOT / "manifests"
    assert Config.BENCHMARK_DATASETS_MANIFEST_PATH == BENCHMARK_DATASETS_MANIFEST_PATH
    assert Config.BENCHMARK_MODELS_MANIFEST_PATH == BENCHMARK_MODELS_MANIFEST_PATH


def test_dataset_manifest_lists_supported_datasets_once():
    payload = load_dataset_manifest()

    assert payload["schema_version"] == "1.0"
    assert payload["benchmark_root"] == "benchmarks"
    assert payload["supported_datasets"] == ["GunPoint", "ECG200", "Wafer", "BasicMotions"]

    names = [item["name"] for item in payload["datasets"]]
    assert names == ["GunPoint", "ECG200", "Wafer", "BasicMotions"]
    assert len(names) == len(set(names))

    gunpoint = next(item for item in payload["datasets"] if item["name"] == "GunPoint")
    assert gunpoint["series_type"] == "univariate"
    assert gunpoint["artifacts"]["train_series_path"] == "datasets/GunPoint/processed/X_train.npy"
    assert not Path(gunpoint["dataset_dir"]).is_absolute()
    assert resolve_benchmark_path(gunpoint["metadata_path"]) == BENCHMARK_ROOT / gunpoint["metadata_path"]


def test_model_manifest_lists_supported_families_and_artifact_locations():
    payload = load_model_manifest()

    assert payload["schema_version"] == "1.0"
    assert payload["supported_model_families"] == ["FCN", "MLP", "InceptionTime"]

    families = [item["family"] for item in payload["families"]]
    assert families == ["fcn", "mlp", "inceptiontime"]

    artifacts = payload["artifacts"]
    assert len(artifacts) == 12

    basic_motions_inception = next(
        item
        for item in artifacts
        if item["family"] == "inceptiontime" and item["dataset"] == "BasicMotions"
    )
    assert basic_motions_inception["status"] == "expected"
    assert basic_motions_inception["artifact_dir"] == "models/weights/inceptiontime/BasicMotions"
    assert basic_motions_inception["input_shape"] == [6, 100]
    assert basic_motions_inception["label_space"] == [
        "Standing",
        "Running",
        "Walking",
        "Badminton",
    ]
