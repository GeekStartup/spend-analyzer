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
        raise HTTPException(status_code=400, detail="secret framework detail")

    @app.get("/secure")
    def secure():
        raise HTTPException(
            status_code=401,
            detail="secret authentication detail",
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.get("/teapot")
    def teapot():
        raise HTTPException(status_code=418, detail={"unsafe": "value"})

    @app.get("/application-error")
    def application_error():
        raise InvalidPdfError(
            "secret file detail",
            context={
                "stage": "validation",
                "status_code": 999,
                "url": "/unsafe-override",
            },
        )

    @app.get("/generic-application-error")
    def generic_application_error():
        raise ApplicationError("secret internal controlled detail")

    @app.get("/boom")
    def boom():
        raise RuntimeError("postgresql://user:password@host/private")

    return app


def test_http_exception_uses_controlled_problem_details_contract():
    response = TestClient(create_test_app()).get(
        "/bad-request?source=secret",
        headers={REQUEST_ID_HEADER: "request-123"},
    )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    assert response.headers[REQUEST_ID_HEADER] == "request-123"
    assert response.json() == {
        "type": "urn:spend-analyzer:problem:invalid-request",
        "title": "Invalid request",
        "status": 400,
        "detail": "The request is invalid.",
        "instance": "urn:spend-analyzer:request:request-123",
        "request_id": "request-123",
        "url": "/bad-request?source=%5BREDACTED%5D",
    }
    assert "secret" not in str(response.json())


def test_problem_response_preserves_http_exception_headers():
    response = TestClient(create_test_app()).get("/secure")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert "secret" not in str(response.json())


def test_not_found_uses_safe_unmatched_url():
    response = TestClient(create_test_app()).get("/private-path?source=secret")

    assert response.status_code == 404
    body = response.json()
    assert body["type"] == "urn:spend-analyzer:problem:not-found"
    assert body["status"] == 404
    assert body["url"] == "/<unmatched>?source=%5BREDACTED%5D"
    assert "private-path" not in str(body)
    assert "secret" not in str(body)


def test_method_not_allowed_preserves_allow_header_and_route_template():
    response = TestClient(create_test_app()).post("/items/private-item")

    assert response.status_code == 405
    assert response.headers["allow"] == "GET"
    assert response.json()["type"] == ("urn:spend-analyzer:problem:method-not-allowed")
    assert response.json()["url"] == "/items/{item_id}"
    assert "private-item" not in str(response.json())


def test_unknown_http_status_uses_safe_fallback_detail():
    response = TestClient(create_test_app()).get("/teapot")

    assert response.status_code == 418
    assert response.json()["type"] == "about:blank"
    assert response.json()["title"] == "HTTP error"
    assert response.json()["detail"] == "The request could not be completed."
    assert "unsafe" not in str(response.json())


def test_validation_problem_excludes_raw_input_and_messages():
    sensitive_input = "account-number-123456789"

    response = TestClient(create_test_app()).get(
        f"/items/{sensitive_input}?page=secret-value"
    )

    assert response.status_code == 422
    body = response.json()
    assert body["type"] == "urn:spend-analyzer:problem:request-validation"
    assert body["detail"] == "One or more request fields are invalid."
    assert body["url"] == "/items/{item_id}?page=%5BREDACTED%5D"
    assert body["errors"]
    assert all(
        set(error) == {"code", "location", "message"} for error in body["errors"]
    )
    assert sensitive_input not in str(body)
    assert "secret-value" not in str(body)


def test_application_error_is_mapped_and_logged_centrally(monkeypatch):
    logger = Mock()
    monkeypatch.setattr("app.problem_details.logger", logger)

    response = TestClient(create_test_app()).get(
        "/application-error",
        headers={REQUEST_ID_HEADER: "request-123"},
    )

    assert response.status_code == 400
    assert response.json()["type"] == "urn:spend-analyzer:problem:invalid-pdf"
    assert response.json()["detail"] == "The uploaded file is not a valid PDF."
    logger.error.assert_called_once_with(
        "Statement ingestion rejected an invalid PDF",
        stage="validation",
        status_code=400,
        problem_type="urn:spend-analyzer:problem:invalid-pdf",
        exception_type="InvalidPdfError",
    )
    assert "secret file detail" not in str(logger.error.call_args)


def test_base_application_error_uses_generic_internal_problem():
    response = TestClient(create_test_app()).get("/generic-application-error")

    assert response.status_code == 500
    assert response.json()["type"] == (
        "urn:spend-analyzer:problem:internal-server-error"
    )
    assert response.json()["detail"] == (
        "Something went wrong. Please try again later."
    )
    assert "secret" not in str(response.json())


def test_unexpected_exception_uses_safe_problem_and_diagnostic_log(monkeypatch):
    logger = Mock()
    exception_metric = Mock()
    monkeypatch.setattr("app.problem_details.logger", logger)
    monkeypatch.setattr("app.problem_details.record_app_exception", exception_metric)

    response = TestClient(create_test_app(), raise_server_exceptions=True).get(
        "/boom?source=secret",
        headers={REQUEST_ID_HEADER: "request-123"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Something went wrong. Please try again later."
    )
    assert response.json()["request_id"] == "request-123"
    assert response.json()["url"] == "/boom?source=%5BREDACTED%5D"
    exception_metric.assert_called_once_with("unhandled")
    logger.error.assert_called_once()
    assert logger.error.call_args.kwargs["status_code"] == 500
    assert logger.error.call_args.kwargs["exception_type"] == "RuntimeError"
    assert "password" not in str(logger.error.call_args)
    assert get_request_id() is None
    assert get_request_url() is None


def test_problem_extensions_cannot_replace_standard_members():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/sample/private",
            "query_string": b"page=secret",
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
    assert b'"url":"/<unmatched>?page=%5BREDACTED%5D"' in response.body
    assert b'"error_code":"invalid_value"' in response.body
    assert b"secret" not in response.body
