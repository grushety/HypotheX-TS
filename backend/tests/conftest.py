import os
from pathlib import Path
import sys
import uuid

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def pytest_configure(config):
    if getattr(config.option, "basetemp", None):
        return

    unique_run_id = f"run-{os.getpid()}-{uuid.uuid4().hex}"
    base_temp_root = BACKEND_DIR / "pytest-tmp-runs"
    base_temp_root.mkdir(parents=True, exist_ok=True)
    config.option.basetemp = str(base_temp_root / unique_run_id)

@pytest.fixture
def app():
    pytest.importorskip("numpy")
    from app.config import TestingConfig
    from app.factory import create_app

    test_app = create_app(TestingConfig)
    yield test_app


@pytest.fixture
def client(app):
    return app.test_client()
