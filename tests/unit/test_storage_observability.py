from contextlib import nullcontext
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from app.api import ingest_routes
from app.auth.dependencies import get_current_user
from app.main import app
from app.schemas.auth_schema import AuthenticatedUser
from app.services import file_storage_service
from app.services.file_storage_service import FileStorageUnavailableError


class EventRecordingSpan:
    def __init__(self):
        self.attributes = {}
        self.events = []
        self.status = None

    def add_event(self, name, attributes=None):
        self.events.append((name, attributes))

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def set_status(self, status):
        self.status = status


def create_upload_file() -> UploadFile:
    return UploadFile(
        filename="statement.pdf",
        file=BytesIO(b"%PDF-1.4 sample content"),
        headers=Headers({"content-type": "application/pdf"}),
    )


def test_save_uploaded_pdf_translates_filesystem_error(monkeypatch, tmp_path):
    sensitive_error = PermissionError(
        "permission denied at /sensitive/user/path/statement.pdf"
    )

    def fail_mkdir(*_args, **_kwargs):
        raise sensitive_error

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)

    with pytest.raises(FileStorageUnavailableError) as error:
        file_storage_service.save_uploaded_pdf(
            file=create_upload_file(),
            upload_dir=str(tmp_path),
            user_id="user-123",
            statement_reference="statement-123",
            content=b"%PDF-1.4 sample content",
            max_upload_size_bytes=10 * 1024 * 1024,
        )

    assert str(error.value) == "File storage is unavailable"
    assert error.value.__cause__ is sensitive_error


def test_ingest_storage_failure_records_safe_observability(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        user_id="user-123",
        username="test.user",
        email="test.user@example.com",
    )

    failure_metric = Mock()
    storage_metric = Mock()
    logger = Mock()
    span = EventRecordingSpan()

    sensitive_error = FileStorageUnavailableError(
        "permission denied at /sensitive/user/path/statement.pdf"
    )

    def fail_save(**_kwargs):
        raise sensitive_error

    monkeypatch.setattr(ingest_routes, "save_uploaded_pdf", fail_save)
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
    monkeypatch.setattr(
        ingest_routes, "start_span", lambda *_args, **_kwargs: nullcontext(span)
    )
    monkeypatch.setattr(ingest_routes, "logger", logger)

    try:
        response = TestClient(app).post(
            "/ingest",
            files={
                "file": (
                    "statement.pdf",
                    b"%PDF-1.4 sample content",
                    "application/pdf",
                )
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "File storage is unavailable"}
    failure_metric.assert_called_once_with(
        ingest_routes.INGESTION_FAILURE_STORAGE_ERROR
    )
    storage_metric.assert_called_once_with(
        ingest_routes.INGESTION_FAILURE_STORAGE_ERROR
    )
    assert span.events == [
        (
            "exception",
            {"exception.type": "FileStorageUnavailableError"},
        )
    ]
    assert "sensitive" not in str(span.events)
    logger.warning.assert_called_once()
    assert "sensitive" not in str(logger.warning.call_args)
