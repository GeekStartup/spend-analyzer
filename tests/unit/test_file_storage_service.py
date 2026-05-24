from io import BytesIO

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.services.file_storage_service import (
    FileStorageError,
    MAX_UPLOAD_SIZE_BYTES,
    save_uploaded_pdf,
    validate_pdf_upload,
)


def create_upload_file(
    *,
    filename: str = "statement.pdf",
    content_type: str = "application/pdf",
) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(b"%PDF-1.4 sample content"),
        headers=Headers({"content-type": content_type}),
    )


def test_validate_pdf_upload_accepts_pdf_file():
    file = create_upload_file()

    validate_pdf_upload(file, b"%PDF-1.4 sample content")


def test_validate_pdf_upload_rejects_non_pdf_extension():
    file = create_upload_file(filename="statement.txt")

    with pytest.raises(FileStorageError) as error:
        validate_pdf_upload(file, b"%PDF-1.4 sample content")

    assert str(error.value) == "Only PDF files are allowed"


def test_validate_pdf_upload_rejects_non_pdf_content_type():
    file = create_upload_file(content_type="text/plain")

    with pytest.raises(FileStorageError) as error:
        validate_pdf_upload(file, b"%PDF-1.4 sample content")

    assert str(error.value) == "Only PDF files are allowed"


def test_validate_pdf_upload_rejects_empty_file():
    file = create_upload_file()

    with pytest.raises(FileStorageError) as error:
        validate_pdf_upload(file, b"")

    assert str(error.value) == "Uploaded file must not be empty"


def test_validate_pdf_upload_rejects_large_file():
    file = create_upload_file()
    large_content = b"%PDF" + b"x" * MAX_UPLOAD_SIZE_BYTES

    with pytest.raises(FileStorageError) as error:
        validate_pdf_upload(file, large_content)

    assert str(error.value) == "Uploaded file exceeds maximum allowed size"


def test_validate_pdf_upload_rejects_invalid_pdf_content():
    file = create_upload_file()

    with pytest.raises(FileStorageError) as error:
        validate_pdf_upload(file, b"not actually a pdf")

    assert str(error.value) == "Uploaded file content is not a valid PDF"


def test_save_uploaded_pdf_uses_generated_file_name(tmp_path):
    file = create_upload_file(filename="statement.pdf")

    stored_file_name, stored_file_path = save_uploaded_pdf(
        file=file,
        upload_dir=str(tmp_path),
        user_id="user-123",
        statement_reference="statement-123",
        content=b"%PDF-1.4 sample content",
    )

    assert stored_file_name.endswith(".pdf")
    assert stored_file_name != "statement.pdf"
    assert stored_file_name.startswith("statement-123-")

    saved_file = tmp_path / "user-123" / stored_file_name

    assert stored_file_path == str(saved_file)
    assert saved_file.exists()
    assert saved_file.read_bytes() == b"%PDF-1.4 sample content"
