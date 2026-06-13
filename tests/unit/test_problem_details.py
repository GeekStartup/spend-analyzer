from unittest.mock import Mock

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.errors import ApplicationError, InvalidPdfError
from app.http import REQUEST_ID_HEADER
from app.observability.context import get_request_id, get_request_url
from app.observability.middleware import RequestContextMiddleware
from app.problem_details import (
    PROBLEM_MEDIA_TYPE,
    create_problem_response,
    register_problem_handlers,
)


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_problem_handlers(app)

    @app.get("/items/{item_id}")
    def read_item(item_id: int, page: int = 1):
        return {"item_id": item_id, "page": page}

    @app.get("/bad-request")
    def bad_request():
        raise HTTPException(status_code=400, detail="Request value is invalid")

    @app.get("/secure")
    def secure():
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.get("/teapot")
    def teapot():
        raise HTTPException(status_code=418, detail={"unsafe": "value"})

    @app.get("/application-error")
    def application_error():
        raise InvalidPdfError(
            "Uploaded file content is not a valid PDF",
            context={
                "stage": "validation",
                "status_code": 999,
                "url": "/unsafe-override",
            },
        )

    @app.get("/generic-application-error")
    def generic_application_error():
        raise ApplicationError("Internal controlled detail")

    @app.get("/boom")
    def boom():
        raise RuntimeError("sensitive internal detail")

    return app


def test_http_exception_uses_problem_details_contract():
    response = TestClient(create_test_app()).get(
        "/bad-request?source=manual",
        headers={REQUEST_ID_HEADER: "request-123"},
    )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    assert response.headers[REQUEST_ID_HEADER] == "request-123"
    assert response.json() == {
        "type": "urn:spend-analyzer:problem:invalid-request",
        "title": "Invalid request",
        "status": 400,
        "detail": "Request value is invalid",
        "instance": "urn:spend-analyzer:request:request-123",
        "request_id": "request-123",
        "url": "/bad-request?source=manual",
    }


def test_problem_response_preserves_http_exception_headers():
    response = TestClient(create_test_app()).get("/secure")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_not_found_uses_problem_details_contract():
    response = TestClient(create_test_app()).get("/missing?source=test")

    assert response.status_code == 404
    body = response.json()
    assert body["type"] == "urn:spend-analyzer:problem:not-found"
    assert body["status"] == 404
    assert body["url"] == "/missing?source=test"


def test_method_not_allowed_preserves_allow_header():
    response = TestClient(create_test_app()).post("/items/123")

    assert response.status_code == 405
    assert response.headers["allow"] == "GET"
    assert response.json()["type"] == (
        "urn:spend-analyzer:problem:method-not-allowed"
    )


def test_unknown_http_status_uses_safe_fallback_detail():
    response = TestClient(create_test_app()).get("/teapot")

    assert response.status_code == 418
    assert response.json()["type"] == "about:blank"
    assert response.json()["title"] == "HTTP error"
    assert response.json()["detail"] == "HTTP error"


def test_validation_problem_excludes_raw_input():
    sensitive_input = "account-number-123456789"

    response = TestClient(create_test_app()).get(
        f"/items/{sensitive_input}?page=not-an-integer"
    )

    assert response.status_code == 422
    body = response.json()
    assert body["type"] == "urn:spend-analyzer:problem:request-validation"
    assert body["detail"] == "One or more request fields are invalid."
    assert body["errors"]
    assert all(
        set(error) == {"code", "location", "message"} for error in body["errors"]
    )
    assert "input" not in str(body["errors"])


def test_application_error_is_mapped_and_logged_centrally(monkeypatch):
    logger = Mock()
    monkeypatch.setattr("app.problem_details.logger", logger)

    response = TestClient(create_test_app()).get(
        "/application-error",
        headers={REQUEST_ID_HEADER: "request-123"},
    )

    assert response.status_code == 400
    assert response.json()["type"] == "urn:spend-analyzer:problem:invalid-pdf"
    assert response.json()["detail"] == "Uploaded file content is not a valid PDF"
    logger.error.assert_called_once_with(
        "Statement ingestion rejected an invalid PDF",
        stage="validation",
        status_code=400,
        problem_type="urn:spend-analyzer:problem:invalid-pdf",
        exception_type="InvalidPdfError",
    )


def test_base_application_error_uses_generic_internal_problem():
    response = TestClient(create_test_app()).get("/generic-application-error")

    assert response.status_code == 500
    assert response.json()["type"] == (
        "urn:spend-analyzer:problem:internal-server-error"
    )
    assert response.json()["detail"] == (
        "Something went wrong. Please try again later."
    )


def test_unexpected_exception_uses_safe_problem_and_diagnostic_log(monkeypatch):
    logger = Mock()
    exception_metric = Mock()
    monkeypatch.setattr("app.problem_details.logger", logger)
    monkeypatch.setattr("app.problem_details.record_app_exception", exception_metric)

    response = TestClient(create_test_app(), raise_server_exceptions=False).get(
        "/boom?source=test",
        headers={REQUEST_ID_HEADER: "request-123"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Something went wrong. Please try again later."
    )
    assert response.json()["request_id"] == "request-123"
    assert response.json()["url"] == "/boom?source=test"
    exception_metric.assert_called_once_with("unhandled")
    logger.error.assert_called_once()
    assert logger.error.call_args.kwargs["status_code"] == 500
    assert logger.error.call_args.kwargs["exception_type"] == "RuntimeError"
    assert "sensitive internal detail" not in str(logger.error.call_args)
    assert get_request_id() is None
    assert get_request_url() is None


def test_problem_extensions_cannot_replace_standard_members():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/sample",
            "query_string": b"page=2",
            "headers": [],
        }
    )

    response = create_problem_response(
        request=request,
        status_code=400,
        detail="Invalid value",
        request_id="request-override",
        extensions={
            "status": 999,
            "url": "/unsafe-override",
            "error_code": "invalid_value",
        },
    )

    assert response.status_code == 400
    assert response.headers[REQUEST_ID_HEADER] == "request-override"
    assert b'"status":400' in response.body
    assert b'"url":"/sample?page=2"' in response.body
    assert b'"error_code":"invalid_value"' in response.body
