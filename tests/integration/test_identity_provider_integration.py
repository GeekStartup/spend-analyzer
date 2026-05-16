import pytest
import requests
from jose import jwt

from tests.support.readiness import wait_for_http_ok


BASE_URL = "http://localhost:58080"
REALM = "spend-analyzer"
EXPECTED_ISSUER = f"{BASE_URL}/realms/{REALM}"
TOKEN_ENDPOINT = f"{EXPECTED_ISSUER}/protocol/openid-connect/token"
DISCOVERY_ENDPOINT = f"{EXPECTED_ISSUER}/.well-known/openid-configuration"


@pytest.mark.integration
def test_identity_provider_exposes_spend_analyzer_realm():
    wait_for_http_ok(DISCOVERY_ENDPOINT)

    response = requests.get(DISCOVERY_ENDPOINT, timeout=5)

    assert response.status_code == 200

    body = response.json()

    assert body["issuer"] == EXPECTED_ISSUER
    assert body["token_endpoint"] == TOKEN_ENDPOINT
    assert "jwks_uri" in body


@pytest.mark.integration
def test_local_test_user_can_generate_access_token():
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

    body = response.json()

    assert body["token_type"] == "Bearer"
    assert body["access_token"]

    claims = jwt.get_unverified_claims(body["access_token"])

    assert claims["iss"] == EXPECTED_ISSUER
    assert claims["preferred_username"] == "test.user"

    audience = claims["aud"]

    if isinstance(audience, str):
        assert audience == "spend-analyzer-api"
    else:
        assert "spend-analyzer-api" in audience
