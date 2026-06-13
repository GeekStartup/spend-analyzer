from io import BytesIO
from unittest.mock import Mock

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app.api import ingest_routes
from app.auth.dependencies import get_current_user
from app.errors import FileStorageError
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


@pytest.mark.anyio
async def test_read_upload_file_with_limit_returns_content():
    file = UploadFile(filename="statement.pdf", file=BytesIO(b"%PDF sample"))

    content = await ingest_routes.read_upload_file_with_limit(file, 1024)

    assert content == b"%PDF sample"


def test_observability_content_type_is_bounded():
    assert ingest_routes.get_observability_content_type("application/pdf") == (
        "application/pdf"
    )
    assert ingest_routes.get_observability_content_type("text/plain") == "unknown"
    assert ingest_routes.get_observability_content_type(None) == "unknown"


def test_upload_too_large_records_failure(client, monkeypatch):
    failure_metric = Mock()
    monkeypatch.setattr(
        ingest_routes,
        "record_statement_ingestion_failure",
        failure_metric,
    )
    monkeypatch.setattr(ingest_routes.settings, "max_upload_size_bytes", 4)

    response = client.post(
        "/ingest",
        files={"file": ("statement.pdf", b"%PDF sample", "application/pdf")},
    )

    assert response.status_code == 413
    failure_metric.assert_called_once_with(
        ingest_routes.INGESTION_FAILURE_UPLOAD_TOO_LARGE
    )


def test_internal_storage_error_records_bounded_metrics(client, monkeypatch):
    ingestion_metric = Mock()
    storage_metric = Mock()

    def fail_storage(**_kwargs):
        raise FileStorageError("internal storage failure")

    monkeypatch.setattr(ingest_routes, "save_uploaded_pdf", fail_storage)
    monkeypatch.setattr(
        ingest_routes,
        "record_statement_ingestion_failure",
        ingestion_metric,
    )
    monkeypatch.setattr(
        ingest_routes,
        "record_file_storage_failure",
        storage_metric,
    )

    response = client.post(
        "/ingest",
        files={"file": ("statement.pdf", b"%PDF sample", "application/pdf")},
    )

    assert response.status_code == 500
    ingestion_metric.assert_called_once_with(
        ingest_routes.INGESTION_FAILURE_STORAGE_INTERNAL_ERROR
    )
    storage_metric.assert_called_once_with(ingest_routes.STORAGE_FAILURE_INTERNAL_ERROR)
