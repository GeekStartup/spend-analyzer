from fastapi.testclient import TestClient

from app.main import app
from app.observability.middleware import REQUEST_ID_HEADER

client = TestClient(app)


def test_app_exposes_metrics_endpoint():
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "# HELP" in response.text
    assert "text/plain" in response.headers["content-type"]


def test_app_adds_request_id_header_to_response():
    response = client.get("/health")

    assert response.status_code == 200
    assert REQUEST_ID_HEADER in response.headers
    assert response.headers[REQUEST_ID_HEADER]


def test_app_preserves_incoming_request_id_header():
    response = client.get(
        "/health",
        headers={REQUEST_ID_HEADER: "request-123"},
    )

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "request-123"


def test_app_lifespan_logs_startup_and_shutdown(monkeypatch):
    info_calls = []
    monkeypatch.setattr(
        "app.main.logger.info",
        lambda *args, **kwargs: info_calls.append((args, kwargs)),
    )

    with TestClient(app) as lifespan_client:
        response = lifespan_client.get("/health")
        assert response.status_code == 200

    assert info_calls == [
        (
            ("Application started",),
            {"environment": "test", "version": "0.1.0"},
        ),
        (
            ("Application stopped",),
            {"environment": "test", "version": "0.1.0"},
        ),
    ]
    assert "change_me" not in str(info_calls)
    assert "postgresql" not in str(info_calls)
