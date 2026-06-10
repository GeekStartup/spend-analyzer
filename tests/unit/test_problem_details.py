from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.http import REQUEST_ID_HEADER
from app.observability.middleware import RequestContextMiddleware
from app.problem_details import PROBLEM_MEDIA_TYPE, register_problem_handlers


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
        set(error) == {"code", "location", "message"}
        for error in body["errors"]
    )
    assert "input" not in str(body["errors"])
