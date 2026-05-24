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
def test_ingest_requires_authentication():
    response = requests.post(
        f"{APP_BASE_URL}/ingest",
        files={
            "file": (
                "statement.pdf",
                b"%PDF-1.4 test statement",
                "application/pdf",
            )
        },
        timeout=10,
    )

    assert response.status_code == 401


@pytest.mark.integration
def test_authenticated_pdf_upload_succeeds():
    token = get_local_access_token()

    response = requests.post(
        f"{APP_BASE_URL}/ingest",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                "statement.pdf",
                b"%PDF-1.4 test statement",
                "application/pdf",
            )
        },
        data={
            "institution": "hdfc",
            "account_type": "credit_card",
            "account_name": "HDFC Millennia",
            "statement_format": "hdfc_credit_card",
        },
        timeout=10,
    )

    assert response.status_code == 201

    body = response.json()

    assert body["statement_reference"]
    assert body["original_file_name"] == "statement.pdf"
    assert body["stored_file_name"].endswith(".pdf")
    assert body["stored_file_name"] != "statement.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["file_size_bytes"] > 0
    assert body["status"] == "UPLOADED"
    assert body["institution"] == "hdfc"
    assert body["account_type"] == "credit_card"
    assert body["account_name"] == "HDFC Millennia"
    assert body["statement_format"] == "hdfc_credit_card"


@pytest.mark.integration
def test_non_pdf_upload_fails():
    token = get_local_access_token()

    response = requests.post(
        f"{APP_BASE_URL}/ingest",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                "statement.txt",
                b"not a pdf",
                "text/plain",
            )
        },
        timeout=10,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF files are allowed"


@pytest.mark.integration
def test_empty_pdf_upload_fails():
    token = get_local_access_token()

    response = requests.post(
        f"{APP_BASE_URL}/ingest",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                "empty.pdf",
                b"",
                "application/pdf",
            )
        },
        timeout=10,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded file must not be empty"


@pytest.mark.integration
def test_fake_pdf_upload_fails():
    token = get_local_access_token()

    response = requests.post(
        f"{APP_BASE_URL}/ingest",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                "fake.pdf",
                b"not actually a pdf",
                "application/pdf",
            )
        },
        timeout=10,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded file content is not a valid PDF"
