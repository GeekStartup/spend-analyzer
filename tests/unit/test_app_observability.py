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
