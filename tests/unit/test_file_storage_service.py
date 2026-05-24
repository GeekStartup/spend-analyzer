from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.services.file_storage_service import (
    FileStorageError,
    UploadTooLargeError,
    create_user_storage_key,
    normalize_content_type,
    save_uploaded_pdf,
    validate_pdf_metadata,
    validate_pdf_upload,
)


TEST_MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


def create_upload_file(
    *,
    filename: str = "statement.pdf",
    content_type: str | None = "application/pdf",
) -> UploadFile:
    headers = Headers({}) if content_type is None else Headers({"content-type": content_type})

    return UploadFile(
        filename=filename,
        file=BytesIO(b"%PDF-1.4 sample content"),
        headers=headers,
    )


def test_normalize_content_type_returns_empty_string_for_missing_value():
    assert normalize_content_type(None) == ""


def test_normalize_content_type_lowercases_mime_type():
    assert normalize_content_type("Application/PDF") == "application/pdf"


def test_normalize_content_type_removes_parameters():
    assert normalize_content_type("application/pdf; charset=binary") == "application/pdf"


def test_validate_pdf_metadata_accepts_pdf_file_with_case_variant_content_type():
    file = create_upload_file(content_type="Application/PDF")

    validate_pdf_metadata(file)


def test_validate_pdf_metadata_accepts_pdf_file_with_content_type_parameters():
    file = create_upload_file(content_type="application/pdf; charset=binary")

    validate_pdf_metadata(file)


def test_validate_pdf_metadata_accepts_pdf_file_without_content_type():
    file = create_upload_file(content_type=None)

    validate_pdf_metadata(file)


def test_validate_pdf_upload_accepts_pdf_file_without_content_type_when_signature_is_valid():
    file = create_upload_file(content_type=None)

    validate_pdf_upload(
        file=file,
        content=b"%PDF-1.4 sample content",
        max_upload_size_bytes=TEST_MAX_UPLOAD_SIZE_BYTES,
    )


def test_validate_pdf_metadata_rejects_non_pdf_extension():
    file = create_upload_file(filename="statement.txt")

    with pytest.raises(FileStorageError) as error:
        validate_pdf_metadata(file)

    assert str(error.value) == "Only PDF files are allowed"


def test_validate_pdf_metadata_rejects_non_pdf_content_type():
    file = create_upload_file(content_type="text/plain")

    with pytest.raises(FileStorageError) as error:
        validate_pdf_metadata(file)

    assert str(error.value) == "Only PDF files are allowed"


def test_validate_pdf_upload_accepts_pdf_file():
    file = create_upload_file()

    validate_pdf_upload(
        file=file,
        content=b"%PDF-1.4 sample content",
        max_upload_size_bytes=TEST_MAX_UPLOAD_SIZE_BYTES,
    )


def test_validate_pdf_upload_rejects_empty_file():
    file = create_upload_file()

    with pytest.raises(FileStorageError) as error:
        validate_pdf_upload(
            file=file,
            content=b"",
            max_upload_size_bytes=TEST_MAX_UPLOAD_SIZE_BYTES,
        )

    assert str(error.value) == "Uploaded file must not be empty"


def test_validate_pdf_upload_rejects_large_file():
    file = create_upload_file()

    with pytest.raises(UploadTooLargeError) as error:
        validate_pdf_upload(
            file=file,
            content=b"%PDF-1.4 sample content",
            max_upload_size_bytes=5,
        )

    assert str(error.value) == "Uploaded file exceeds maximum allowed size"


def test_validate_pdf_upload_rejects_invalid_pdf_content():
    file = create_upload_file()

    with pytest.raises(FileStorageError) as error:
        validate_pdf_upload(
            file=file,
            content=b"not actually a pdf",
            max_upload_size_bytes=TEST_MAX_UPLOAD_SIZE_BYTES,
        )

    assert str(error.value) == "Uploaded file content is not a valid PDF"


def test_create_user_storage_key_hashes_user_id():
    user_id = "../../outside"
    storage_key = create_user_storage_key(user_id)

    assert storage_key != user_id
    assert "/" not in storage_key
    assert "\\" not in storage_key
    assert len(storage_key) == 64


def test_save_uploaded_pdf_uses_generated_file_name_and_safe_user_folder(tmp_path):
    file = create_upload_file(filename="statement.pdf")
    user_id = "../../outside"

    stored_file_name, stored_file_path = save_uploaded_pdf(
        file=file,
        upload_dir=str(tmp_path),
        user_id=user_id,
        statement_reference="statement-123",
        content=b"%PDF-1.4 sample content",
        max_upload_size_bytes=TEST_MAX_UPLOAD_SIZE_BYTES,
    )

    assert stored_file_name.endswith(".pdf")
    assert stored_file_name != "statement.pdf"
    assert stored_file_name.startswith("statement-123-")

    expected_user_folder = tmp_path / create_user_storage_key(user_id)
    saved_file = expected_user_folder / stored_file_name

    assert stored_file_path == str(saved_file.resolve())
    assert saved_file.exists()
    assert saved_file.read_bytes() == b"%PDF-1.4 sample content"
    assert Path(stored_file_path).resolve().is_relative_to(tmp_path.resolve())
