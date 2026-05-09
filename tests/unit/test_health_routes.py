from fastapi.testclient import TestClient
from psycopg import OperationalError

from app.main import app


client = TestClient(app)


def test_health_check_returns_application_status():
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "OK"
    assert body["service"] == "Spend Analyzer"
    assert body["environment"] == "test"
    assert body["version"] == "0.1.0"


def test_database_health_check_returns_ok_when_database_is_reachable(monkeypatch):
    def fake_check_database_connection():
        return True

    monkeypatch.setattr(
        "app.api.health_routes.check_database_connection",
        fake_check_database_connection,
    )

    response = client.get("/health/db")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "OK"
    assert body["service"] == "database"
    assert body["message"] == "Database is reachable"


def test_database_health_check_returns_503_when_database_is_unreachable(monkeypatch):
    def fake_check_database_connection():
        raise OperationalError("database unavailable")

    monkeypatch.setattr(
        "app.api.health_routes.check_database_connection",
        fake_check_database_connection,
    )

    response = client.get("/health/db")

    assert response.status_code == 503

    body = response.json()

    assert body["detail"]["status"] == "ERROR"
    assert body["detail"]["service"] == "database"
    assert body["detail"]["message"] == "Database is not reachable"
    assert body["detail"]["error"] == "OperationalError"
