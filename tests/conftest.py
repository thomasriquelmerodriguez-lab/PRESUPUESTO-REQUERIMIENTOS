import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB = Path(__file__).parent / "test.db"
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{TEST_DB}"
os.environ["APP_ORIGIN"] = "http://testserver"
os.environ["SECRET_KEY"] = "test-secret-key-with-at-least-32-characters"
os.environ["AUTO_CREATE_SCHEMA"] = "true"
os.environ["SEED_ON_STARTUP"] = "true"
os.environ["SECURE_COOKIES"] = "false"

from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def clean_database():
    TEST_DB.unlink(missing_ok=True)
    yield
    TEST_DB.unlink(missing_ok=True)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, username: str = "encargado de presupuesto") -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "2026"},
        headers={"origin": "http://testserver"},
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]
