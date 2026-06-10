from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_route_and_metrics_route_are_both_available():
    assert client.get("/health").status_code == 200
    assert client.get("/metrics").status_code == 200
