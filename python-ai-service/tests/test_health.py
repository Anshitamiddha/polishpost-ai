from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    settings = get_settings()

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


def test_health_exists_only_under_the_v1_prefix():
    assert client.get("/health").status_code == 404


def test_interactive_docs_are_served():
    assert client.get("/docs").status_code == 200
