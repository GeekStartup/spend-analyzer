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

    @app.get("/context")
    def context():
        return {"request_id": get_request_id(), "url": get_request_url()}

    @app.get("/bad-request")
    def bad_request():
        raise HTTPException(status_code=400, detail="Invalid request")

    return app


def test_middleware_binds_request_context_and_header():
    response = TestClient(create_test_app()).get(
        "/context?source=test",
        headers={REQUEST_ID_HEADER: "request-123"},
    )

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "request-123"
    assert response.json() == {
        "request_id": "request-123",
        "url": "/context?source=test",
    }
    assert get_request_id() is None
    assert get_request_url() is None


def test_middleware_logs_success_as_info(monkeypatch):
    logger = Mock()
    monkeypatch.setattr("app.observability.middleware.logger", logger)

    response = TestClient(create_test_app()).get("/context")

    assert response.status_code == 200
    logger.info.assert_called_once()
    logger.error.assert_not_called()
    assert logger.info.call_args.kwargs["status_code"] == 200


def test_middleware_logs_client_error_as_error(monkeypatch):
    logger = Mock()
    monkeypatch.setattr("app.observability.middleware.logger", logger)

    response = TestClient(create_test_app()).get("/bad-request")

    assert response.status_code == 400
    logger.error.assert_called_once()
    logger.info.assert_not_called()
    assert logger.error.call_args.kwargs["status_code"] == 400
