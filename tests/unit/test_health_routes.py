from contextlib import nullcontext
from unittest.mock import Mock

from fastapi.testclient import TestClient
from opentelemetry.trace import StatusCode
from psycopg import OperationalError

from app.http import REQUEST_ID_HEADER
from app.main import app

client = TestClient(app)


class FakeSpan:
    def __init__(self):
        self.attributes = {}
        self.exceptions = []
        self.status = None

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def record_exception(self, error):
        self.exceptions.append(error)

    def set_status(self, status):
        self.status = status


def patch_database_health_observability(monkeypatch):
    dependency_health_metric = Mock()
    logger = Mock()
    span = FakeSpan()
    start_span = Mock(return_value=nullcontext(span))

    monkeypatch.setattr(
        "app.api.health_routes.record_dependency_health",
        dependency_health_metric,
    )
    monkeypatch.setattr("app.api.health_routes.start_span", start_span)
    monkeypatch.setattr("app.api.health_routes.logger", logger)

    return {
        "dependency_health_metric": dependency_health_metric,
        "logger": logger,
        "span": span,
        "start_span": start_span,
    }


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


def test_database_health_check_records_healthy_observability(monkeypatch):
    observability = patch_database_health_observability(monkeypatch)
    monkeypatch.setattr(
        "app.api.health_routes.check_database_connection",
        lambda: True,
    )

    response = client.get("/health/db")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "OK"
    assert_service_metadata(body)
    assert body["checks"]["database"]["status"] == "OK"
    assert body["checks"]["database"]["message"] == "Database is reachable"
    observability["dependency_health_metric"].assert_called_once_with(
        "database",
        True,
    )
    observability["start_span"].assert_called_once_with(
        "database.health_check",
        attributes={"app.dependency.name": "database"},
    )
    assert observability["span"].attributes == {"app.outcome": "healthy"}
    assert observability["span"].exceptions == []
    assert observability["span"].status is None
    observability["logger"].warning.assert_not_called()


def test_database_health_connection_error_returns_problem_details(monkeypatch):
    observability = patch_database_health_observability(monkeypatch)
    sensitive_error_message = (
        "connection failed for "
        "postgresql://database-user:database-password@database.internal:5432/spend"
    )
    database_error = OperationalError(sensitive_error_message)

    def fail_database_check():
        raise database_error

    monkeypatch.setattr(
        "app.api.health_routes.check_database_connection",
        fail_database_check,
    )
    monkeypatch.setattr(
        "app.api.health_routes.perf_counter",
        Mock(side_effect=[1.0, 1.25]),
    )

    response = client.get(
        "/health/db",
        headers={REQUEST_ID_HEADER: "request-123"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "type": "urn:spend-analyzer:problem:database-unavailable",
        "title": "Database unavailable",
        "status": 503,
        "detail": "The database health check could not be completed.",
        "instance": "urn:spend-analyzer:request:request-123",
        "request_id": "request-123",
        "url": "/health/db",
    }
    observability["dependency_health_metric"].assert_called_once_with(
        "database",
        False,
    )
    assert observability["span"].exceptions == [database_error]
    assert observability["span"].status.status_code == StatusCode.ERROR
    assert observability["span"].attributes == {
        "app.outcome": "unhealthy",
        "app.failure.category": "connection_error",
    }
    observability["logger"].warning.assert_called_once_with(
        "Database health check failed",
        dependency="database",
        operation="health_check",
        duration_ms=250.0,
        exception_type="OperationalError",
    )
    assert sensitive_error_message not in str(observability["logger"].warning.call_args)


def test_database_health_unhealthy_result_returns_problem_details(monkeypatch):
    observability = patch_database_health_observability(monkeypatch)
    monkeypatch.setattr(
        "app.api.health_routes.check_database_connection",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.api.health_routes.perf_counter",
        Mock(side_effect=[1.0, 1.01]),
    )

    response = client.get(
        "/health/db",
        headers={REQUEST_ID_HEADER: "request-123"},
    )

    assert response.status_code == 503
    assert response.json()["type"] == (
        "urn:spend-analyzer:problem:database-unavailable"
    )
    assert response.json()["request_id"] == "request-123"
    observability["dependency_health_metric"].assert_called_once_with(
        "database",
        False,
    )
    assert observability["span"].exceptions == []
    assert observability["span"].status.status_code == StatusCode.ERROR
    assert observability["span"].attributes == {
        "app.outcome": "unhealthy",
        "app.failure.category": "health_check_failed",
    }
    observability["logger"].warning.assert_called_once_with(
        "Database health check returned an unhealthy result",
        dependency="database",
        operation="health_check",
        duration_ms=10.0,
    )
