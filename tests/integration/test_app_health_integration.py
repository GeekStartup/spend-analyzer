import pytest
import requests


BASE_URL = "http://localhost:18000"
EXPECTED_SERVICE = {
    "name": "Spend Analyzer",
    "environment": "test",
    "version": "0.1.0",
}


@pytest.mark.integration
def test_app_health_endpoint_works_through_running_container():
    response = requests.get(BASE_URL + "/health", timeout=5)

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "OK"
    assert body["service"] == EXPECTED_SERVICE
    assert body["checks"]["application"] == {
        "status": "OK",
        "message": "Application is running",
    }


@pytest.mark.integration
def test_database_health_endpoint_connects_from_app_container_to_db_container():
    response = requests.get(BASE_URL + "/health/db", timeout=5)

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "OK"
    assert body["service"] == EXPECTED_SERVICE
    assert body["checks"]["database"] == {
        "status": "OK",
        "message": "Database is reachable",
    }
