from pathlib import Path
import sys

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.factory import create_app
from app.config import TestingConfig


@pytest.fixture
def app():
    test_app = create_app(TestingConfig)
    yield test_app


@pytest.fixture
def client(app):
    return app.test_client()
