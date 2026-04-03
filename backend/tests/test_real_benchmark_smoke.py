from app.config import TestingConfig
from app.core.benchmark_manifest import load_model_manifest
from app.factory import create_app


def create_real_benchmark_client():
    app = create_app(TestingConfig)
    return app.test_client()


def assert_stage_ok(response, stage):
    payload = response.get_json(silent=True)
    assert response.status_code == 200, (
        f"Smoke stage '{stage}' failed with status {response.status_code}: {payload}"
    )
    return payload


def test_univariate_real_benchmark_smoke_path():
    client = create_real_benchmark_client()

    datasets_payload = assert_stage_ok(client.get("/api/benchmarks/datasets"), "registry:datasets")
    dataset_names = {dataset["name"] for dataset in datasets_payload["datasets"]}
    assert "GunPoint" in dataset_names, "Smoke stage 'registry:datasets' did not expose GunPoint."

    models_payload = assert_stage_ok(client.get("/api/benchmarks/models"), "registry:models")
    artifact_ids = {artifact["artifact_id"] for artifact in models_payload["artifacts"]}
    assert "fcn-gunpoint" in artifact_ids, "Smoke stage 'registry:models' did not expose fcn-gunpoint."

    compatibility_payload = assert_stage_ok(
        client.get("/api/benchmarks/compatibility?dataset=GunPoint&artifact_id=fcn-gunpoint"),
        "validation:compatibility",
    )
    assert compatibility_payload["is_compatible"] is True, (
        "Smoke stage 'validation:compatibility' marked GunPoint and fcn-gunpoint incompatible."
    )

    sample_payload = assert_stage_ok(
        client.get("/api/benchmarks/sample?dataset=GunPoint&split=test&sample_index=0"),
        "sample:load",
    )
    assert sample_payload["dataset_name"] == "GunPoint"
    assert sample_payload["series_type"] == "univariate"
    assert sample_payload["channel_count"] == 1
    assert sample_payload["series_length"] == 150
    assert len(sample_payload["values"]) == 1
    assert len(sample_payload["values"][0]) == 150

    prediction_payload = assert_stage_ok(
        client.get("/api/benchmarks/prediction?dataset=GunPoint&artifact_id=fcn-gunpoint&split=test&sample_index=0"),
        "prediction:run",
    )
    assert prediction_payload["dataset_name"] == "GunPoint"
    assert prediction_payload["artifact_id"] == "fcn-gunpoint"
    assert prediction_payload["split"] == "test"
    assert prediction_payload["sample_index"] == 0
    assert prediction_payload["predicted_label"] in {"1", "2"}
    assert len(prediction_payload["scores"]) == 2


def test_wafer_prediction_smoke_path_uses_shipped_fcn_artifact():
    client = create_real_benchmark_client()

    compatibility_payload = assert_stage_ok(
        client.get("/api/benchmarks/compatibility?dataset=Wafer&artifact_id=fcn-wafer"),
        "validation:compatibility-wafer",
    )
    assert compatibility_payload["is_compatible"] is True, (
        "Smoke stage 'validation:compatibility-wafer' marked Wafer and fcn-wafer incompatible."
    )

    sample_payload = assert_stage_ok(
        client.get("/api/benchmarks/sample?dataset=Wafer&split=test&sample_index=0"),
        "sample:load-wafer",
    )
    assert sample_payload["dataset_name"] == "Wafer"
    assert sample_payload["series_type"] == "univariate"
    assert sample_payload["channel_count"] == 1
    assert sample_payload["series_length"] == 152
    assert len(sample_payload["values"]) == 1
    assert len(sample_payload["values"][0]) == 152

    prediction_payload = assert_stage_ok(
        client.get("/api/benchmarks/prediction?dataset=Wafer&artifact_id=fcn-wafer&split=test&sample_index=0"),
        "prediction:run-wafer",
    )
    assert prediction_payload["dataset_name"] == "Wafer"
    assert prediction_payload["artifact_id"] == "fcn-wafer"
    assert prediction_payload["split"] == "test"
    assert prediction_payload["sample_index"] == 0
    assert prediction_payload["predicted_label"] in {"1", "-1"}
    assert len(prediction_payload["scores"]) == 2


def test_all_manifest_artifacts_support_prediction_smoke_path():
    client = create_real_benchmark_client()
    manifest = load_model_manifest()

    for artifact in manifest["artifacts"]:
        dataset_name = artifact["dataset"]
        artifact_id = artifact["artifact_id"]
        label_space = artifact["label_space"]

        compatibility_payload = assert_stage_ok(
            client.get(f"/api/benchmarks/compatibility?dataset={dataset_name}&artifact_id={artifact_id}"),
            f"validation:compatibility:{artifact_id}",
        )
        assert compatibility_payload["is_compatible"] is True, (
            f"Smoke stage 'validation:compatibility:{artifact_id}' marked {dataset_name} and {artifact_id} incompatible."
        )

        sample_payload = assert_stage_ok(
            client.get(f"/api/benchmarks/sample?dataset={dataset_name}&split=test&sample_index=0"),
            f"sample:load:{dataset_name}",
        )
        assert sample_payload["dataset_name"] == dataset_name

        prediction_payload = assert_stage_ok(
            client.get(
                f"/api/benchmarks/prediction?dataset={dataset_name}&artifact_id={artifact_id}&split=test&sample_index=0"
            ),
            f"prediction:run:{artifact_id}",
        )
        assert prediction_payload["dataset_name"] == dataset_name
        assert prediction_payload["artifact_id"] == artifact_id
        assert prediction_payload["split"] == "test"
        assert prediction_payload["sample_index"] == 0
        assert prediction_payload["predicted_label"] in set(label_space)
        assert len(prediction_payload["scores"]) == len(label_space)
