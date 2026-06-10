from contextlib import nullcontext
from io import BytesIO
from unittest.mock import Mock

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from opentelemetry.trace import StatusCode

from app.api.ingest_routes import (
    INGESTION_FAILURE_FILE_VALIDATION_OR_STORAGE,
    INGESTION_FAILURE_UPLOAD_TOO_LARGE,
    normalize_optional_text,
    read_upload_file_with_limit,
)
from app.auth.dependencies import get_current_user
from app.main import app
from app.schemas.auth_schema import AuthenticatedUser
from app.services.file_storage_service import FileStorageError, UploadTooLargeError


class FakeSpan:
    """
    Minimal OpenTelemetry span replacement used by route tests.

    It records only the operations that the ingestion route performs:
    attributes, exceptions, and final status.
    """

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
    """
    Replace metrics, tracing, and logging with controllable test doubles.

    Returning all doubles lets each test assert only the behavior relevant
    to its success or failure path.
    """
    attempt_metric = Mock()
    success_metric = Mock()
    failure_metric = Mock()
    logger = Mock()

    span = FakeSpan()
    start_span = Mock(return_value=nullcontext(span))

    monkeypatch.setattr(
        "app.api.ingest_routes.record_statement_ingestion_attempt",
        attempt_metric,
    )
    monkeypatch.setattr(
        "app.api.ingest_routes.record_statement_ingestion_success",
        success_metric,
    )
    monkeypatch.setattr(
        "app.api.ingest_routes.record_statement_ingestion_failure",
        failure_metric,
    )
    monkeypatch.setattr(
        "app.api.ingest_routes.start_span",
        start_span,
    )
    monkeypatch.setattr(
        "app.api.ingest_routes.logger",
        logger,
    )

    return {
        "attempt_metric": attempt_metric,
        "success_metric": success_metric,
        "failure_metric": failure_metric,
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

    monkeypatch.setattr(
        "app.api.ingest_routes.save_uploaded_pdf",
        fake_save_uploaded_pdf,
    )
    monkeypatch.setattr(
        "app.api.ingest_routes.uuid4",
        lambda: "statement-123",
    )

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

    observability["attempt_metric"].assert_called_once_with()

    observability["success_metric"].assert_called_once_with(
        content_type="application/pdf",
        file_size_bytes=len(b"%PDF-1.4 sample content"),
    )

    observability["failure_metric"].assert_not_called()

    observability["start_span"].assert_called_once_with(
        "statement.ingestion",
        attributes={
            "app.statement.reference": "statement-123",
            "app.statement.content_type": "application/pdf",
        },
    )

    assert observability["span"].attributes["app.outcome"] == "succeeded"
    assert observability["span"].attributes["app.statement.file_size_bytes"] == len(
        b"%PDF-1.4 sample content"
    )
    assert observability["span"].exceptions == []
    assert observability["span"].status is None

    observability["logger"].info.assert_called_once_with(
        "statement.ingestion",
        outcome="succeeded",
        statement_reference="statement-123",
        content_type="application/pdf",
        file_size_bytes=len(b"%PDF-1.4 sample content"),
    )

    observability["logger"].warning.assert_not_called()


def test_upload_statement_records_upload_too_large_failure(client, monkeypatch):
    observability = patch_ingestion_observability(monkeypatch)

    monkeypatch.setattr(
        "app.api.ingest_routes.settings.max_upload_size_bytes",
        5,
    )
    monkeypatch.setattr(
        "app.api.ingest_routes.uuid4",
        lambda: "statement-123",
    )

    response = client.post(
        "/ingest",
        files={
            "file": (
                "statement.pdf",
                b"%PDF-1.4 sample content",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "Uploaded file exceeds maximum allowed size",
    }

    observability["attempt_metric"].assert_called_once_with()
    observability["success_metric"].assert_not_called()

    observability["failure_metric"].assert_called_once_with(
        INGESTION_FAILURE_UPLOAD_TOO_LARGE
    )

    observability["start_span"].assert_called_once_with(
        "statement.ingestion",
        attributes={
            "app.statement.reference": "statement-123",
            "app.statement.content_type": "application/pdf",
        },
    )

    assert len(observability["span"].exceptions) == 1
    assert isinstance(
        observability["span"].exceptions[0],
        UploadTooLargeError,
    )

    assert observability["span"].status.status_code == StatusCode.ERROR
    assert (
        observability["span"].status.description == INGESTION_FAILURE_UPLOAD_TOO_LARGE
    )
    assert observability["span"].attributes["app.outcome"] == "failed"
    assert (
        observability["span"].attributes["app.failure.category"]
        == INGESTION_FAILURE_UPLOAD_TOO_LARGE
    )

    observability["logger"].warning.assert_called_once_with(
        "statement.ingestion",
        outcome="failed",
        statement_reference="statement-123",
        failure_category=INGESTION_FAILURE_UPLOAD_TOO_LARGE,
        exception_type="UploadTooLargeError",
    )

    observability["logger"].info.assert_not_called()


def test_upload_statement_records_storage_validation_failure(client, monkeypatch):
    observability = patch_ingestion_observability(monkeypatch)

    def fake_save_uploaded_pdf(**kwargs):
        raise FileStorageError("storage failed")

    monkeypatch.setattr(
        "app.api.ingest_routes.save_uploaded_pdf",
        fake_save_uploaded_pdf,
    )
    monkeypatch.setattr(
        "app.api.ingest_routes.uuid4",
        lambda: "statement-123",
    )

    response = client.post(
        "/ingest",
        files={
            "file": (
                "statement.pdf",
                b"%PDF-1.4 sample content",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "storage failed",
    }

    observability["attempt_metric"].assert_called_once_with()
    observability["success_metric"].assert_not_called()

    observability["failure_metric"].assert_called_once_with(
        INGESTION_FAILURE_FILE_VALIDATION_OR_STORAGE
    )

    assert len(observability["span"].exceptions) == 1
    assert isinstance(
        observability["span"].exceptions[0],
        FileStorageError,
    )

    assert observability["span"].status.status_code == StatusCode.ERROR
    assert (
        observability["span"].status.description
        == INGESTION_FAILURE_FILE_VALIDATION_OR_STORAGE
    )
    assert observability["span"].attributes["app.outcome"] == "failed"
    assert (
        observability["span"].attributes["app.failure.category"]
        == INGESTION_FAILURE_FILE_VALIDATION_OR_STORAGE
    )

    observability["logger"].warning.assert_called_once_with(
        "statement.ingestion",
        outcome="failed",
        statement_reference="statement-123",
        failure_category=INGESTION_FAILURE_FILE_VALIDATION_OR_STORAGE,
        exception_type="FileStorageError",
    )

    observability["logger"].info.assert_not_called()
