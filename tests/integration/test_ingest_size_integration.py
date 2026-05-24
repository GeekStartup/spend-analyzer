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
DEFAULT_MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


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
def test_valid_pdf_larger_than_one_mb_succeeds():
    token = get_local_access_token()
    pdf_content = b"%PDF-1.4\n" + b"x" * (2 * 1024 * 1024)

    response = requests.post(
        f"{APP_BASE_URL}/ingest",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                "large-statement.pdf",
                pdf_content,
                "application/pdf",
            )
        },
        timeout=20,
    )

    assert response.status_code == 201
    assert response.json()["file_size_bytes"] == len(pdf_content)


@pytest.mark.integration
def test_oversized_pdf_upload_returns_413():
    token = get_local_access_token()
    pdf_content = b"%PDF-1.4\n" + b"x" * DEFAULT_MAX_UPLOAD_SIZE_BYTES

    response = requests.post(
        f"{APP_BASE_URL}/ingest",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                "oversized.pdf",
                pdf_content,
                "application/pdf",
            )
        },
        timeout=20,
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Uploaded file exceeds maximum allowed size"
