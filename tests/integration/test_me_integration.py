import pytest
import requests

from tests.support.readiness import wait_for_http_ok


APP_BASE_URL = "http://localhost:18000"
KEYCLOAK_BASE_URL = "http://localhost:58080"
REALM = "spend-analyzer"
TOKEN_ENDPOINT = f"{KEYCLOAK_BASE_URL}/realms/{REALM}/protocol/openid-connect/token"
DISCOVERY_ENDPOINT = (
    f"{KEYCLOAK_BASE_URL}/realms/{REALM}/.well-known/openid-configuration"
)


def get_local_access_token() -> str:
    wait_for_http_ok(DISCOVERY_ENDPOINT)

    response = requests.post(
        TOKEN_ENDPOINT,
        data={
            "grant_type": "password",
            "client_id": "spend-analyzer-local",
            "username": "test.user",
            "password": "change_me",
        },
        timeout=10,
    )

    assert response.status_code == 200

    return response.json()["access_token"]


@pytest.mark.integration
def test_me_returns_401_without_token():
    response = requests.get(f"{APP_BASE_URL}/me", timeout=5)

    assert response.status_code == 401


@pytest.mark.integration
def test_me_returns_authenticated_user_for_valid_token():
    token = get_local_access_token()

    response = requests.get(
        f"{APP_BASE_URL}/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["user_id"]
    assert body["username"] == "test.user"
    assert body["email"] == "test.user@example.com"


@pytest.mark.integration
def test_me_returns_401_for_malformed_token():
    response = requests.get(
        f"{APP_BASE_URL}/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
        timeout=5,
    )

    assert response.status_code == 401
