from app.config import TestingConfig
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


def test_multivariate_smoke_localizes_missing_artifact_to_prediction_stage():
    client = create_real_benchmark_client()

    compatibility_payload = assert_stage_ok(
        client.get("/api/benchmarks/compatibility?dataset=BasicMotions&artifact_id=fcn-basicmotions"),
        "validation:compatibility-multivariate",
    )
    assert compatibility_payload["is_compatible"] is True, (
        "Smoke stage 'validation:compatibility-multivariate' unexpectedly failed before artifact loading."
    )

    sample_payload = assert_stage_ok(
        client.get("/api/benchmarks/sample?dataset=BasicMotions&split=test&sample_index=0"),
        "sample:load-multivariate",
    )
    assert sample_payload["dataset_name"] == "BasicMotions"
    assert sample_payload["series_type"] == "multivariate"
    assert sample_payload["channel_count"] == 6
    assert len(sample_payload["values"]) == 6
    assert len(sample_payload["values"][0]) == 100

    response = client.get(
        "/api/benchmarks/prediction?dataset=BasicMotions&artifact_id=fcn-basicmotions&split=test&sample_index=0"
    )

    assert response.status_code == 500, (
        "Smoke stage 'prediction:run-multivariate' should currently fail until a real BasicMotions artifact is added."
    )
    payload = response.get_json()
    assert "Model artifact directory does not exist" in payload["error"], (
        "Smoke stage 'prediction:run-multivariate' did not localize the failure to missing model artifacts."
    )
