import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.observability.context import get_request_id
from app.observability.middleware import (
    REQUEST_ID_HEADER,
    RequestContextMiddleware,
    _get_route_path,
    _should_log_request,
)


def create_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)

    @test_app.get("/context")
    def read_context():
        return {"request_id": get_request_id()}

    return test_app


def test_middleware_generates_request_id_when_header_is_missing():
    client = TestClient(create_test_app())

    response = client.get("/context")

    assert response.status_code == 200
    assert REQUEST_ID_HEADER in response.headers
    assert response.json()["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_middleware_preserves_existing_request_id_header():
    client = TestClient(create_test_app())

    response = client.get(
        "/context",
        headers={REQUEST_ID_HEADER: "request-123"},
    )

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "request-123"
    assert response.json()["request_id"] == "request-123"


@pytest.mark.parametrize(
    "unsafe_request_id",
    [
        "contains spaces",
        "x" * 129,
        "../../account-data",
    ],
)
def test_middleware_replaces_unsafe_request_id_header(
    unsafe_request_id,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.observability.middleware.uuid4",
        lambda: "generated-request-id",
    )
    client = TestClient(create_test_app())

    response = client.get(
        "/context",
        headers={REQUEST_ID_HEADER: unsafe_request_id},
    )

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "generated-request-id"
    assert response.json()["request_id"] == "generated-request-id"
    assert unsafe_request_id not in response.text


def test_middleware_clears_request_context_after_request():
    client = TestClient(create_test_app())

    response = client.get("/context")

    assert response.status_code == 200
    assert get_request_id() is None


def test_middleware_records_unhandled_exception_and_returns_request_id(monkeypatch):
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)

    recorded_categories = []

    def fake_record_app_exception(exception_category: str) -> None:
        recorded_categories.append(exception_category)

    monkeypatch.setattr(
        "app.observability.middleware.record_app_exception",
        fake_record_app_exception,
    )

    @test_app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    client = TestClient(test_app, raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER]
    assert response.json() == {"detail": "Internal Server Error"}
    assert recorded_categories == ["unhandled"]
    assert get_request_id() is None


def test_middleware_preserves_existing_request_id_header_on_unhandled_exception(
    monkeypatch,
):
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)

    monkeypatch.setattr(
        "app.observability.middleware.record_app_exception",
        lambda _exception_category: None,
    )

    @test_app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    client = TestClient(test_app, raise_server_exceptions=False)

    response = client.get(
        "/boom",
        headers={REQUEST_ID_HEADER: "request-123"},
    )

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER] == "request-123"
    assert get_request_id() is None


def test_get_route_path_returns_unmatched_when_route_is_missing():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/missing",
            "headers": [],
        }
    )

    assert _get_route_path(request) == "unmatched"


def test_should_log_request_skips_configured_metrics_route():
    assert _should_log_request("/internal/metrics", "/internal/metrics") is False


def test_should_log_request_allows_non_metrics_route():
    assert _should_log_request("/health", "/metrics") is True


def test_middleware_skips_request_log_for_configured_metrics_route(monkeypatch):
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware, metrics_path="/internal/metrics")

    log_calls = []

    def fake_info(*args, **kwargs):
        log_calls.append((args, kwargs))

    monkeypatch.setattr(
        "app.observability.middleware.logger.info",
        fake_info,
    )

    @test_app.get("/internal/metrics")
    def metrics():
        return "metrics"

    client = TestClient(test_app)

    response = client.get("/internal/metrics")

    assert response.status_code == 200
    assert log_calls == []
