from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.services import file_storage_service
from app.services.file_storage_service import FileStorageUnavailableError


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
