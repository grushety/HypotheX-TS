"""Route tests for ``POST /api/donors/propose`` (HTS-104)."""
from __future__ import annotations

import json

import numpy as np
import pytest

from app.config import TestingConfig
from app.factory import create_app
from app.services.datasets import DatasetRegistry


def _make_dataset_manifest(tmp_path):
    """Tiny two-class GunPoint-shaped dataset for donor ranking tests."""
    dataset_dir = tmp_path / "benchmarks" / "datasets" / "GunPoint" / "processed"
    dataset_dir.mkdir(parents=True)
    train_series = np.asarray(
        [
            [[0.0, 0.0, 0.0]],
            [[0.1, 0.1, 0.1]],
            [[1.0, 1.0, 1.0]],
            [[1.1, 1.1, 1.1]],
            [[1.2, 1.2, 1.2]],
        ],
        dtype=np.float32,
    )
    train_labels = np.asarray([0, 0, 1, 1, 1], dtype=np.int64)
    test_series = np.asarray([[[0.05, 0.05, 0.05]]], dtype=np.float32)
    test_labels = np.asarray([0], dtype=np.int64)

    np.save(dataset_dir / "X_train.npy", train_series)
    np.save(dataset_dir / "y_train.npy", train_labels)
    np.save(dataset_dir / "X_test.npy", test_series)
    np.save(dataset_dir / "y_test.npy", test_labels)

    return {
        "datasets": [
            {
                "name": "GunPoint",
                "status": "prepared",
                "task_type": "classification",
                "series_type": "univariate",
                "dataset_dir": str(tmp_path / "benchmarks" / "datasets" / "GunPoint"),
                "raw_dir": str(tmp_path / "benchmarks" / "datasets" / "GunPoint" / "raw"),
                "processed_dir": str(dataset_dir),
                "metadata_path": str(tmp_path / "benchmarks" / "datasets" / "GunPoint" / "metadata.json"),
                "summary_path": str(dataset_dir / "summary.json"),
                "source_archive": "univariate_ts",
                "source": "test source",
                "license": None,
                "notes": "test dataset",
                "n_channels": 1,
                "train_shape": [5, 1, 3],
                "test_shape": [1, 1, 3],
                "n_classes": 2,
                "classes": ["class-0", "class-1"],
                "export_format": "npy",
                "tensor_layout": "n_samples x n_channels x series_length",
                "artifacts": {
                    "train_series_path": str(dataset_dir / "X_train.npy"),
                    "train_labels_path": str(dataset_dir / "y_train.npy"),
                    "test_series_path": str(dataset_dir / "X_test.npy"),
                    "test_labels_path": str(dataset_dir / "y_test.npy"),
                },
            }
        ]
    }


@pytest.fixture
def donor_client(tmp_path):
    registry = DatasetRegistry(manifest=_make_dataset_manifest(tmp_path))
    app = create_app(TestingConfig)
    app.config["DATASET_REGISTRY"] = registry
    return app.test_client()


def _base_payload(**overrides):
    payload = {
        "backend": "NativeGuide",
        "segment_values": [1.05, 1.05, 1.05],
        "target_class": "class-1",
        "dataset": "GunPoint",
        "k": 0,
        "exclude_ids": [],
    }
    payload.update(overrides)
    return payload


def test_native_guide_happy_path(donor_client):
    rv = donor_client.post("/api/donors/propose", json=_base_payload())
    assert rv.status_code == 200, rv.get_json()
    body = rv.get_json()
    assert body["backend"] == "NativeGuide"
    assert len(body["candidates"]) == 1
    cand = body["candidates"][0]
    assert cand["donor_id"].startswith("native_guide:")
    assert cand["metric"] == "dtw"
    assert isinstance(cand["values"], list) and len(cand["values"]) == 3
    assert cand["distance"] >= 0


def test_native_guide_with_exclude_ids(donor_client):
    first = donor_client.post("/api/donors/propose", json=_base_payload(k=0))
    first_donor_id = first.get_json()["candidates"][0]["donor_id"]
    rv = donor_client.post("/api/donors/propose", json=_base_payload(
        exclude_ids=[first_donor_id],
    ))
    assert rv.status_code == 200
    body = rv.get_json()
    assert len(body["candidates"]) == 1
    assert body["candidates"][0]["donor_id"] != first_donor_id


def test_native_guide_with_k_greater_than_one(donor_client):
    # class-1 has 3 examples → k=2 returns the third-closest
    rv = donor_client.post("/api/donors/propose", json=_base_payload(k=2))
    assert rv.status_code == 200
    assert len(rv.get_json()["candidates"]) == 1
    # k beyond the corpus → empty
    rv = donor_client.post("/api/donors/propose", json=_base_payload(k=10))
    assert rv.status_code == 200
    assert rv.get_json()["candidates"] == []


@pytest.mark.parametrize("backend", ["SETSDonor", "DiscordDonor", "TimeGAN", "ShapeDBA"])
def test_unsupported_backends_return_501(donor_client, backend):
    rv = donor_client.post("/api/donors/propose", json=_base_payload(backend=backend))
    assert rv.status_code == 501
    body = rv.get_json()
    assert backend in body["error"]
    assert body["supported"] == ["NativeGuide", "UserDrawn"]


def test_user_drawn_returns_400(donor_client):
    rv = donor_client.post("/api/donors/propose", json=_base_payload(backend="UserDrawn"))
    assert rv.status_code == 400


def test_malformed_payload_returns_400(donor_client):
    # missing segment_values
    rv = donor_client.post("/api/donors/propose", json={"backend": "NativeGuide"})
    assert rv.status_code == 400
    # not an object
    rv = donor_client.post(
        "/api/donors/propose",
        data="not json",
        headers={"Content-Type": "application/json"},
    )
    assert rv.status_code == 400
