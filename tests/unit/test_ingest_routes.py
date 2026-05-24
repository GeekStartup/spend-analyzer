from io import BytesIO

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app.api.ingest_routes import normalize_optional_text, read_upload_file_with_limit
from app.auth.dependencies import get_current_user
from app.main import app
from app.schemas.auth_schema import AuthenticatedUser
from app.services.file_storage_service import FileStorageError, UploadTooLargeError


def create_upload_file(content: bytes) -> UploadFile:
    return UploadFile(filename="statement.pdf", file=BytesIO(content))


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        user_id="user-123",
        username="test.user",
        email="test.user@example.com",
    )

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_normalize_optional_text_returns_none_for_missing_value():
    assert normalize_optional_text(None) is None


def test_normalize_optional_text_returns_none_for_blank_value():
    assert normalize_optional_text("   ") is None


def test_normalize_optional_text_trims_value():
    assert normalize_optional_text("  hdfc  ") == "hdfc"


@pytest.mark.anyio
async def test_read_upload_file_with_limit_returns_content_within_limit():
    file = create_upload_file(b"%PDF-1.4 sample content")

    content = await read_upload_file_with_limit(file, 1024)

    assert content == b"%PDF-1.4 sample content"


@pytest.mark.anyio
async def test_read_upload_file_with_limit_rejects_content_above_limit():
    file = create_upload_file(b"%PDF-1.4 sample content")

    with pytest.raises(UploadTooLargeError) as error:
        await read_upload_file_with_limit(file, 5)

    assert str(error.value) == "Uploaded file exceeds maximum allowed size"


def test_upload_statement_returns_created_response(client, monkeypatch):
    def fake_save_uploaded_pdf(**kwargs):
        assert kwargs["user_id"] == "user-123"
        assert kwargs["content"] == b"%PDF-1.4 sample content"

        return "stored-statement.pdf", "/tmp/stored-statement.pdf"

    monkeypatch.setattr(
        "app.api.ingest_routes.save_uploaded_pdf", fake_save_uploaded_pdf
    )
    monkeypatch.setattr("app.api.ingest_routes.uuid4", lambda: "statement-123")

    response = client.post(
        "/ingest",
        files={
            "file": ("statement.pdf", b"%PDF-1.4 sample content", "application/pdf")
        },
        data={
            "institution": "  HDFC  ",
            "account_type": "  savings  ",
            "account_name": "  primary  ",
            "statement_format": "  pdf  ",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "statement_reference": "statement-123",
        "original_file_name": "statement.pdf",
        "stored_file_name": "stored-statement.pdf",
        "content_type": "application/pdf",
        "file_size_bytes": len(b"%PDF-1.4 sample content"),
        "status": "UPLOADED",
        "institution": "HDFC",
        "account_type": "savings",
        "account_name": "primary",
        "statement_format": "pdf",
    }


def test_upload_statement_returns_413_for_large_file(client, monkeypatch):
    monkeypatch.setattr("app.api.ingest_routes.settings.max_upload_size_bytes", 5)

    response = client.post(
        "/ingest",
        files={
            "file": ("statement.pdf", b"%PDF-1.4 sample content", "application/pdf")
        },
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "Uploaded file exceeds maximum allowed size",
    }


def test_upload_statement_returns_400_for_storage_validation_error(client, monkeypatch):
    def fake_save_uploaded_pdf(**kwargs):
        raise FileStorageError("storage failed")

    monkeypatch.setattr(
        "app.api.ingest_routes.save_uploaded_pdf", fake_save_uploaded_pdf
    )

    response = client.post(
        "/ingest",
        files={
            "file": ("statement.pdf", b"%PDF-1.4 sample content", "application/pdf")
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "storage failed"}
