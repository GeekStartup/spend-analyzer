from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import InvalidPdfError
from app.http import REQUEST_ID_HEADER
from app.observability.middleware import RequestContextMiddleware
from app.problem_details import register_problem_handlers


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_problem_handlers(app)

    @app.get("/application-error")
    def application_error():
        raise InvalidPdfError(
            "Uploaded file content is not a valid PDF",
            context={"operation": "statement_ingestion", "stage": "validation"},
        )

    @app.get("/unexpected-error")
    def unexpected_error():
        raise RuntimeError("internal diagnostic detail")

    return app


def test_application_error_is_mapped_and_logged_centrally(monkeypatch):
    logger = Mock()
    monkeypatch.setattr("app.problem_details.logger", logger)

    response = TestClient(create_test_app()).get(
        "/application-error",
        headers={REQUEST_ID_HEADER: "request-123"},
    )

    assert response.status_code == 400
    assert response.json()["type"] == "urn:spend-analyzer:problem:invalid-pdf"
    assert response.json()["url"] == "/application-error"
    assert logger.error.call_args.kwargs["operation"] == "statement_ingestion"
    assert logger.error.call_args.kwargs["stage"] == "validation"


def test_unexpected_error_uses_safe_problem_and_log(monkeypatch):
    logger = Mock()
    exception_metric = Mock()
    monkeypatch.setattr("app.problem_details.logger", logger)
    monkeypatch.setattr(
        "app.problem_details.record_app_exception",
        exception_metric,
    )

    response = TestClient(
        create_test_app(),
        raise_server_exceptions=False,
    ).get("/unexpected-error")

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Something went wrong. Please try again later."
    )
    exception_metric.assert_called_once_with("unhandled")
    assert logger.error.call_args.kwargs["exception_type"] == "RuntimeError"
    assert "internal diagnostic detail" not in str(logger.error.call_args)
