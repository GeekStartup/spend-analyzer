from unittest.mock import Mock

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.http import REQUEST_ID_HEADER
from app.observability.context import get_request_id, get_request_url
from app.observability.middleware import RequestContextMiddleware
from app.problem_details import register_problem_handlers


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_problem_handlers(app)

    @app.get("/context/{item_id}")
    def context(item_id: str):
        return {
            "item_id": item_id,
            "request_id": get_request_id(),
            "url": get_request_url(),
        }

    @app.get("/bad-request")
    def bad_request():
        raise HTTPException(status_code=400, detail="uncontrolled detail")

    @app.get("/boom")
    def boom():
        raise RuntimeError("internal occurrence detail")

    return app


def test_middleware_binds_only_correlation_context_and_header():
    response = TestClient(create_test_app()).get(
        "/context/item-value?source=query-value",
        headers={REQUEST_ID_HEADER: "request-123"},
    )

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "request-123"
    assert response.json() == {
        "item_id": "item-value",
        "request_id": "request-123",
        "url": None,
    }
    assert get_request_id() is None
    assert get_request_url() is None


def test_middleware_logs_safe_success_outcome(monkeypatch):
    logger = Mock()
    monkeypatch.setattr("app.observability.middleware.logger", logger)

    response = TestClient(create_test_app()).get(
        "/context/item-value?source=query-value"
    )

    assert response.status_code == 200
    logger.info.assert_called_once()
    logger.error.assert_not_called()
    fields = logger.info.call_args.kwargs
    assert fields["status_code"] == 200
    assert fields["url"] == "/context/{item_id}?source=%5BREDACTED%5D"
    assert "item-value" not in str(logger.info.call_args)
    assert "query-value" not in str(logger.info.call_args)


def test_middleware_logs_client_error_as_error(monkeypatch):
    logger = Mock()
    monkeypatch.setattr("app.observability.middleware.logger", logger)

    response = TestClient(create_test_app()).get("/bad-request")

    assert response.status_code == 400
    logger.error.assert_called_once()
    logger.info.assert_not_called()
    assert logger.error.call_args.kwargs["status_code"] == 400


def test_middleware_contains_unexpected_exception(monkeypatch):
    logger = Mock()
    monkeypatch.setattr("app.observability.middleware.logger", logger)

    response = TestClient(create_test_app(), raise_server_exceptions=True).get(
        "/boom?source=query-value",
        headers={REQUEST_ID_HEADER: "request-123"},
    )

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER] == "request-123"
    assert response.json()["request_id"] == "request-123"
    assert response.json()["url"] == "/boom?source=%5BREDACTED%5D"
    logger.error.assert_called_once()
    assert logger.error.call_args.kwargs["status_code"] == 500
    assert "internal occurrence detail" not in str(logger.error.call_args)
