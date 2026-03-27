from collections.abc import Mapping
from pathlib import Path
from typing import Any


def build_health_payload(config: Mapping[str, Any]) -> dict[str, Any]:
    benchmark_root = Path(config["BENCHMARK_ROOT"])
    database_uri = str(config["SQLALCHEMY_DATABASE_URI"])
    return {
        "status": "ok",
        "service": "backend",
        "database": {
            "engine": "sqlite",
            "uri": database_uri,
        },
        "paths": {
            "benchmark_root": str(benchmark_root),
        },
    }
