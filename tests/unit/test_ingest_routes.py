from contextlib import nullcontext
from io import BytesIO
from unittest.mock import Mock

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from opentelemetry.trace import StatusCode

from app.api import ingest_routes
from app.api.ingest_routes import normalize_optional_text, read_upload_file_with_limit
from app.auth.dependencies import get_current_user
from app.http import REQUEST_ID_HEADER
from app.main import app
from app.schemas.auth_schema import AuthenticatedUser
from app.services.file_storage_service import (
    FileStorageError,
    FileStorageUnavailableError,
    UploadTooLargeError,
)


class FakeSpan:
    def __init__(self):
        self.attributes = {}
        self.exceptions = []
        self.status = None

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def record_exception(self, error):
        self.exceptions.append(error)

    def set_status(self, status):
        self.status = status


def create_upload_file(content: bytes) -> UploadFile:
    return UploadFile(
        filename="statement.pdf",
        file=BytesIO(content),
    )


def patch_ingestion_observability(monkeypatch):
    attempt_metric = Mock()
    success_metric = Mock()
    failure_metric = Mock()
    storage_metric = Mock()
    logger = Mock()
    span = FakeSpan()
    start_span = Mock(return_value=nullcontext(span))

    monkeypatch.setattr(
        ingest_routes,
        "record_statement_ingestion_attempt",
        attempt_metric,
    )
    monkeypatch.setattr(
        ingest_routes,
        "record_statement_ingestion_success",
        success_metric,
    )
    monkeypatch.setattr(
        ingest_routes,
        "record_statement_ingestion_failure",
        failure_metric,
    )
    monkeypatch.setattr(
        ingest_routes,
        "record_file_storage_failure",
        storage_metric,
    )
    monkeypatch.setattr(ingest_routes, "start_span", start_span)
    monkeypatch.setattr(ingest_routes, "logger", logger)

    return {
        "attempt_metric": attempt_metric,
        "success_metric": success_metric,
        "failure_metric": failure_metric,
        "storage_metric": storage_metric,
        "logger": logger,
        "span": span,
        "start_span": start_span,
    }


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


def test_upload_statement_records_success_observability(client, monkeypatch):
    observability = patch_ingestion_observability(monkeypatch)

    def fake_save_uploaded_pdf(**kwargs):
        assert kwargs["user_id"] == "user-123"
        assert kwargs["content"] == b"%PDF-1.4 sample content"
        return "stored-statement.pdf", "/tmp/stored-statement.pdf"

    monkeypatch.setattr(ingest_routes, "save_uploaded_pdf", fake_save_uploaded_pdf)
    monkeypatch.setattr(ingest_routes, "uuid4", lambda: "statement-123")

    response = client.post(
        "/ingest",
        files={
            "file": (
                "statement.pdf",
                b"%PDF-1.4 sample content",
                "application/pdf",
            )
        },
        data={
            "institution": "  HDFC  ",
            "account_type": "  savings  ",
            "account_name": "  primary  ",
            "statement_format": "  pdf  ",
        },
    )

    assert response.status_code == 201
    assert response.json()["statement_reference"] == "statement-123"
    assert response.json()["institution"] == "HDFC"
    observability["attempt_metric"].assert_called_once_with()
    observability["success_metric"].assert_called_once_with(
        content_type="application/pdf",
        file_size_bytes=len(b"%PDF-1.4 sample content"),
    )
    observability["failure_metric"].assert_not_called()
    observability["storage_metric"].assert_not_called()
    observability["start_span"].assert_called_once_with(
        "statement.ingestion",
        attributes={
            "app.statement.reference": "statement-123",
            "app.statement.content_type": "application/pdf",
        },
    )
    assert observability["span"].attributes["app.outcome"] == "succeeded"
    assert observability["span"].exceptions == []
    assert observability["span"].status is None
    observability["logger"].debug.assert_called_once_with(
        "Statement upload content read",
        statement_reference="statement-123",
        file_size_bytes=len(b"%PDF-1.4 sample content"),
    )
    observability["logger"].info.assert_called_once_with(
        "Statement ingestion succeeded",
        statement_reference="statement-123",
        content_type="application/pdf",
        file_size_bytes=len(b"%PDF-1.4 sample content"),
    )


def test_upload_statement_records_upload_too_large_failure(client, monkeypatch):
    observability = patch_ingestion_observability(monkeypatch)
    monkeypatch.setattr(ingest_routes.settings, "max_upload_size_bytes", 5)
    monkeypatch.setattr(ingest_routes, "uuid4", lambda: "statement-123")

    response = client.post(
        "/ingest",
        headers={REQUEST_ID_HEADER: "request-123"},
        files={
            "file": (
                "statement.pdf",
                b"%PDF-1.4 sample content",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert response.json()["type"] == "urn:spend-analyzer:problem:upload-too-large"
    assert response.json()["request_id"] == "request-123"
    observability["failure_metric"].assert_called_once_with(
        ingest_routes.INGESTION_FAILURE_UPLOAD_TOO_LARGE
    )
    observability["storage_metric"].assert_not_called()
    assert observability["span"].status.status_code == StatusCode.ERROR
    observability["logger"].info.assert_called_once_with(
        "Statement ingestion rejected an oversized upload",
        statement_reference="statement-123",
        stage="upload",
        configured_max_size_bytes=5,
        exception_type="UploadTooLargeError",
    )


def test_upload_statement_records_invalid_pdf_failure(client, monkeypatch):
    observability = patch_ingestion_observability(monkeypatch)
    monkeypatch.setattr(ingest_routes, "uuid4", lambda: "statement-123")

    response = client.post(
        "/ingest",
        headers={REQUEST_ID_HEADER: "request-123"},
        files={"file": ("statement.txt", b"not a pdf", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["type"] == "urn:spend-analyzer:problem:invalid-pdf"
    observability["failure_metric"].assert_called_once_with(
        ingest_routes.INGESTION_FAILURE_INVALID_PDF
    )
    observability["storage_metric"].assert_not_called()
    observability["logger"].info.assert_called_once_with(
        "Statement ingestion rejected an invalid PDF",
        statement_reference="statement-123",
        stage="validation",
        exception_type="InvalidPdfError",
    )


def test_upload_statement_records_storage_unavailable_failure(client, monkeypatch):
    observability = patch_ingestion_observability(monkeypatch)
    sensitive_error = FileStorageUnavailableError(
        "permission denied at /sensitive/user/path/statement.pdf"
    )

    def fail_save(**_kwargs):
        raise sensitive_error

    monkeypatch.setattr(ingest_routes, "save_uploaded_pdf", fail_save)
    monkeypatch.setattr(ingest_routes, "uuid4", lambda: "statement-123")

    response = client.post(
        "/ingest",
        headers={REQUEST_ID_HEADER: "request-123"},
        files={
            "file": (
                "statement.pdf",
                b"%PDF-1.4 sample content",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 503
    assert response.json()["type"] == (
        "urn:spend-analyzer:problem:file-storage-unavailable"
    )
    observability["failure_metric"].assert_called_once_with(
        ingest_routes.INGESTION_FAILURE_STORAGE_UNAVAILABLE
    )
    observability["storage_metric"].assert_called_once_with(
        ingest_routes.STORAGE_FAILURE_UNAVAILABLE
    )
    observability["logger"].warning.assert_called_once_with(
        "Statement ingestion failed because file storage is unavailable",
        statement_reference="statement-123",
        stage="storage",
        exception_type="FileStorageUnavailableError",
    )
    assert "sensitive" not in str(observability["logger"].warning.call_args)


def test_upload_statement_records_internal_storage_failure(client, monkeypatch):
    observability = patch_ingestion_observability(monkeypatch)
    sensitive_error = FileStorageError("internal path /sensitive/storage")

    def fail_save(**_kwargs):
        raise sensitive_error

    monkeypatch.setattr(ingest_routes, "save_uploaded_pdf", fail_save)
    monkeypatch.setattr(ingest_routes, "uuid4", lambda: "statement-123")

    response = client.post(
        "/ingest",
        headers={REQUEST_ID_HEADER: "request-123"},
        files={
            "file": (
                "statement.pdf",
                b"%PDF-1.4 sample content",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 500
    assert response.json()["type"] == (
        "urn:spend-analyzer:problem:internal-server-error"
    )
    observability["failure_metric"].assert_called_once_with(
        ingest_routes.INGESTION_FAILURE_STORAGE_INTERNAL_ERROR
    )
    observability["storage_metric"].assert_called_once_with(
        ingest_routes.STORAGE_FAILURE_INTERNAL_ERROR
    )
    observability["logger"].error.assert_called_once_with(
        "Statement ingestion failed because of an unexpected storage error",
        statement_reference="statement-123",
        stage="storage",
        exception_type="FileStorageError",
    )
    assert "sensitive" not in str(observability["logger"].error.call_args)
