from app.core.paths import BENCHMARK_ROOT


def test_app_uses_testing_config(app):
    assert app.config["TESTING"] is True
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def test_health_endpoint_returns_expected_payload(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {
        "status": "ok",
        "service": "backend",
        "database": {
            "engine": "sqlite",
            "uri": "sqlite:///:memory:",
        },
        "paths": {
            "benchmark_root": str(BENCHMARK_ROOT),
        },
    }
