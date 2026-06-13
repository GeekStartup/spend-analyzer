from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_application_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "OK"


def test_database_health_records_healthy_dependency(monkeypatch):
    metric = Mock()
    monkeypatch.setattr(
        "app.api.health_routes.check_database_connection",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.api.health_routes.record_dependency_health",
        metric,
    )

    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json()["checks"]["database"]["status"] == "OK"
    metric.assert_called_once_with("database", True)


def test_database_unhealthy_result_uses_problem_details(monkeypatch):
    metric = Mock()
    monkeypatch.setattr(
        "app.api.health_routes.check_database_connection",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.api.health_routes.record_dependency_health",
        metric,
    )

    response = client.get("/health/db")

    assert response.status_code == 503
    assert response.json()["type"] == (
        "urn:spend-analyzer:problem:database-unavailable"
    )
    metric.assert_called_once_with("database", False)
