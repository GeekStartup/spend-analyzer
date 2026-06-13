from io import BytesIO
from unittest.mock import Mock

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app.api import ingest_routes
from app.api.ingest_routes import normalize_optional_text, read_upload_file_with_limit
from app.auth.dependencies import get_current_user
from app.errors import FileStorageUnavailableError, UploadTooLargeError
from app.main import app
from app.schemas.auth_schema import AuthenticatedUser


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        user_id="user-123"
    )
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_normalize_optional_text():
    assert normalize_optional_text(None) is None
    assert normalize_optional_text("   ") is None
    assert normalize_optional_text("  HDFC  ") == "HDFC"


@pytest.mark.anyio
async def test_read_upload_file_with_limit_rejects_large_content():
    file = UploadFile(filename="statement.pdf", file=BytesIO(b"%PDF sample"))

    with pytest.raises(UploadTooLargeError):
        await read_upload_file_with_limit(file, 4)


def patch_observability(monkeypatch):
    values = {
        "attempt": Mock(),
        "success": Mock(),
        "failure": Mock(),
        "storage": Mock(),
        "logger": Mock(),
    }
    monkeypatch.setattr(
        ingest_routes,
        "record_statement_ingestion_attempt",
        values["attempt"],
    )
    monkeypatch.setattr(
        ingest_routes,
        "record_statement_ingestion_success",
        values["success"],
    )
    monkeypatch.setattr(
        ingest_routes,
        "record_statement_ingestion_failure",
        values["failure"],
    )
    monkeypatch.setattr(
        ingest_routes,
        "record_file_storage_failure",
        values["storage"],
    )
    monkeypatch.setattr(ingest_routes, "logger", values["logger"])
    return values


def test_upload_statement_records_success(client, monkeypatch):
    values = patch_observability(monkeypatch)
    monkeypatch.setattr(ingest_routes, "uuid4", lambda: "statement-123")
    monkeypatch.setattr(
        ingest_routes,
        "save_uploaded_pdf",
        lambda **_kwargs: ("stored.pdf", "/tmp/stored.pdf"),
    )

    response = client.post(
        "/ingest",
        files={"file": ("statement.pdf", b"%PDF sample", "application/pdf")},
    )

    assert response.status_code == 201
    values["attempt"].assert_called_once_with()
    values["success"].assert_called_once_with(
        content_type="application/pdf",
        file_size_bytes=len(b"%PDF sample"),
    )
    values["logger"].info.assert_called_once()


def test_upload_statement_records_invalid_pdf(client, monkeypatch):
    values = patch_observability(monkeypatch)

    response = client.post(
        "/ingest",
        files={"file": ("statement.txt", b"not-pdf", "text/plain")},
    )

    assert response.status_code == 400
    values["failure"].assert_called_once_with(
        ingest_routes.INGESTION_FAILURE_INVALID_PDF
    )


def test_upload_statement_records_storage_unavailable(client, monkeypatch):
    values = patch_observability(monkeypatch)

    def fail_save(**_kwargs):
        raise FileStorageUnavailableError("Storage is unavailable")

    monkeypatch.setattr(ingest_routes, "save_uploaded_pdf", fail_save)

    response = client.post(
        "/ingest",
        files={"file": ("statement.pdf", b"%PDF sample", "application/pdf")},
    )

    assert response.status_code == 503
    values["failure"].assert_called_once_with(
        ingest_routes.INGESTION_FAILURE_STORAGE_UNAVAILABLE
    )
    values["storage"].assert_called_once_with(
        ingest_routes.STORAGE_FAILURE_UNAVAILABLE
    )
