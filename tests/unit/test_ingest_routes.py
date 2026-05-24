from io import BytesIO

import pytest
from fastapi import UploadFile

from app.api.ingest_routes import normalize_optional_text, read_upload_file_with_limit
from app.services.file_storage_service import FileStorageError


def create_upload_file(content: bytes) -> UploadFile:
    return UploadFile(filename="statement.pdf", file=BytesIO(content))


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

    with pytest.raises(FileStorageError) as error:
        await read_upload_file_with_limit(file, 5)

    assert str(error.value) == "Uploaded file exceeds maximum allowed size"
