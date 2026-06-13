from unittest.mock import Mock

from fastapi.testclient import TestClient
from psycopg import OperationalError

from app.main import app


def test_database_connection_error_uses_typed_problem(monkeypatch):
    dependency_metric = Mock()

    def fail_database_check():
        raise OperationalError("database connection failed")

    monkeypatch.setattr(
        "app.api.health_routes.check_database_connection",
        fail_database_check,
    )
    monkeypatch.setattr(
        "app.api.health_routes.record_dependency_health",
        dependency_metric,
    )

    response = TestClient(app).get("/health/db")

    assert response.status_code == 503
    assert response.json()["type"] == (
        "urn:spend-analyzer:problem:database-unavailable"
    )
    dependency_metric.assert_called_once_with("database", False)
