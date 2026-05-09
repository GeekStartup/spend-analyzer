import pytest
import requests


BASE_URL = "http://localhost:18000"


@pytest.mark.integration
def test_app_health_endpoint_works_through_running_container():
    response = requests.get(f"{BASE_URL}/health", timeout=5)

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "OK"
    assert body["service"] == "Spend Analyzer"
    assert body["environment"] == "test"
    assert body["version"] == "0.1.0"


@pytest.mark.integration
def test_database_health_endpoint_connects_from_app_container_to_db_container():
    response = requests.get(f"{BASE_URL}/health/db", timeout=5)

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "OK"
    assert body["service"] == "database"
    assert body["message"] == "Database is reachable"
