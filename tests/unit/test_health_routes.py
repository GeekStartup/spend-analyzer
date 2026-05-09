from fastapi.testclient import TestClient
from psycopg import OperationalError

from app.main import app


client = TestClient(app)


def assert_service_metadata(body):
    assert body["service"]["name"] == "Spend Analyzer"
    assert body["service"]["environment"] == "test"
    assert body["service"]["version"] == "0.1.0"


def test_health_check_returns_application_status():
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "OK"
    assert_service_metadata(body)
    assert body["checks"]["application"]["status"] == "OK"
    assert body["checks"]["application"]["message"] == "Application is running"


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
    assert_service_metadata(body)
    assert body["checks"]["database"]["status"] == "OK"
    assert body["checks"]["database"]["message"] == "Database is reachable"


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

    assert body["status"] == "ERROR"
    assert_service_metadata(body)
    assert body["checks"]["database"]["status"] == "ERROR"
    assert body["checks"]["database"]["message"] == "Database is not reachable"
    assert body["checks"]["database"]["error"] == "OperationalError"


def test_database_health_check_returns_503_when_database_health_check_fails(monkeypatch):
    def fake_check_database_connection():
        return False

    monkeypatch.setattr(
        "app.api.health_routes.check_database_connection",
        fake_check_database_connection,
    )

    response = client.get("/health/db")

    assert response.status_code == 503

    body = response.json()

    assert body["status"] == "ERROR"
    assert_service_metadata(body)
    assert body["checks"]["database"]["status"] == "ERROR"
    assert body["checks"]["database"]["message"] == "Database health check failed"
