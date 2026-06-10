from contextlib import nullcontext
from unittest.mock import Mock

from fastapi.testclient import TestClient
from opentelemetry.trace import StatusCode
from psycopg import OperationalError

from app.main import app

client = TestClient(app)


class FakeSpan:
    """
    Minimal OpenTelemetry span replacement used by route tests.

    It records only the operations performed by the database-health route:
    attributes, exceptions, and final status.
    """

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
    """
    Replace database-health metrics, tracing, and logging with test doubles.

    Each route test can then verify the observability side effects produced
    by its specific success or failure path.
    """
    dependency_health_metric = Mock()
    logger = Mock()

    span = FakeSpan()
    start_span = Mock(return_value=nullcontext(span))

    monkeypatch.setattr(
        "app.api.health_routes.record_dependency_health",
        dependency_health_metric,
    )
    monkeypatch.setattr(
        "app.api.health_routes.start_span",
        start_span,
    )
    monkeypatch.setattr(
        "app.api.health_routes.logger",
        logger,
    )

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


def test_database_health_check_records_healthy_observability(
    monkeypatch,
):
    observability = patch_database_health_observability(monkeypatch)

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

    observability["dependency_health_metric"].assert_called_once_with(
        "database",
        True,
    )

    observability["start_span"].assert_called_once_with(
        "database.health_check",
        attributes={
            "app.dependency.name": "database",
        },
    )

    assert observability["span"].attributes == {
        "app.outcome": "healthy",
    }
    assert observability["span"].exceptions == []
    assert observability["span"].status is None

    observability["logger"].warning.assert_not_called()
    observability["logger"].info.assert_not_called()


def test_database_health_check_records_connection_error_observability(
    monkeypatch,
):
    observability = patch_database_health_observability(monkeypatch)

    sensitive_error_message = (
        "connection failed for "
        "postgresql://database-user:database-password@database.internal:5432/spend"
    )
    database_error = OperationalError(sensitive_error_message)

    def fake_check_database_connection():
        raise database_error

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

    observability["dependency_health_metric"].assert_called_once_with(
        "database",
        False,
    )

    observability["start_span"].assert_called_once_with(
        "database.health_check",
        attributes={
            "app.dependency.name": "database",
        },
    )

    assert observability["span"].exceptions == [database_error]
    assert observability["span"].status.status_code == StatusCode.ERROR
    assert observability["span"].status.description == "connection_error"
    assert observability["span"].attributes == {
        "app.outcome": "unhealthy",
        "app.failure.category": "connection_error",
    }

    observability["logger"].warning.assert_called_once_with(
        "database.health_check",
        outcome="unhealthy",
        failure_category="connection_error",
        exception_type="OperationalError",
    )
    observability["logger"].info.assert_not_called()

    assert sensitive_error_message not in str(observability["logger"].warning.call_args)


def test_database_health_check_records_failed_check_observability(
    monkeypatch,
):
    observability = patch_database_health_observability(monkeypatch)

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

    observability["dependency_health_metric"].assert_called_once_with(
        "database",
        False,
    )

    observability["start_span"].assert_called_once_with(
        "database.health_check",
        attributes={
            "app.dependency.name": "database",
        },
    )

    assert observability["span"].exceptions == []
    assert observability["span"].status.status_code == StatusCode.ERROR
    assert observability["span"].status.description == "health_check_failed"
    assert observability["span"].attributes == {
        "app.outcome": "unhealthy",
        "app.failure.category": "health_check_failed",
    }

    observability["logger"].warning.assert_called_once_with(
        "database.health_check",
        outcome="unhealthy",
        failure_category="health_check_failed",
    )
    observability["logger"].info.assert_not_called()
