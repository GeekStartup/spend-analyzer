import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.http import REQUEST_ID_HEADER, get_relative_url
from app.observability.context import get_request_id
from app.observability.middleware import RequestContextMiddleware, _should_log_request


def create_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)

    @test_app.get("/context")
    def read_context():
        return {"request_id": get_request_id()}

    @test_app.get("/items/{item_id}")
    def read_item(item_id: str):
        return {"item_id": item_id}

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


def test_middleware_records_unhandled_exception_as_problem_details(monkeypatch):
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
        raise RuntimeError("sensitive database-password=secret")

    client = TestClient(test_app, raise_server_exceptions=False)

    response = client.get(
        "/boom?source=test",
        headers={REQUEST_ID_HEADER: "request-123"},
    )

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER] == "request-123"
    assert response.json() == {
        "type": "urn:spend-analyzer:problem:internal-server-error",
        "title": "Internal server error",
        "status": 500,
        "detail": "The request could not be completed.",
        "instance": "urn:spend-analyzer:request:request-123",
        "request_id": "request-123",
        "url": "/boom?source=test",
    }
    assert "database-password" not in response.text
    assert recorded_categories == ["unhandled"]
    assert get_request_id() is None


def test_get_relative_url_includes_path_and_query_without_host():
    request = Request(
        {
            "type": "http",
            "scheme": "https",
            "server": ("api.example.com", 443),
            "method": "GET",
            "path": "/items/item-123",
            "query_string": b"page=2&status=pending",
            "headers": [(b"host", b"api.example.com")],
        }
    )

    assert get_relative_url(request) == "/items/item-123?page=2&status=pending"


def test_get_relative_url_omits_query_separator_when_query_is_empty():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "query_string": b"",
            "headers": [],
        }
    )

    assert get_relative_url(request) == "/health"


def test_middleware_logs_actual_relative_url(monkeypatch):
    log_calls = []
    monkeypatch.setattr(
        "app.observability.middleware.logger.info",
        lambda *args, **kwargs: log_calls.append((args, kwargs)),
    )

    response = TestClient(create_test_app()).get(
        "/items/item-123?page=2",
    )

    assert response.status_code == 200
    assert len(log_calls) == 1
    assert log_calls[0][0] == ("http.request",)
    assert log_calls[0][1]["url"] == "/items/item-123?page=2"
    assert "route" not in log_calls[0][1]


def test_should_log_request_skips_configured_metrics_route():
    assert _should_log_request("/internal/metrics", "/internal/metrics") is False


def test_should_log_request_allows_non_metrics_route():
    assert _should_log_request("/health", "/metrics") is True


def test_middleware_skips_request_log_for_configured_metrics_route(monkeypatch):
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware, metrics_path="/internal/metrics")

    log_calls = []
    monkeypatch.setattr(
        "app.observability.middleware.logger.info",
        lambda *args, **kwargs: log_calls.append((args, kwargs)),
    )

    @test_app.get("/internal/metrics")
    def metrics():
        return "metrics"

    response = TestClient(test_app).get("/internal/metrics?probe=true")

    assert response.status_code == 200
    assert log_calls == []
