import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}
PDF_EXTENSION = ".pdf"
PDF_SIGNATURE = b"%PDF"


class FileStorageError(Exception):
    """
    Raised when uploaded file validation or storage fails.
    """


class UploadTooLargeError(FileStorageError):
    """
    Raised when uploaded file exceeds the configured maximum size.
    """


def normalize_content_type(content_type: str | None) -> str:
    if not content_type:
        return ""

    return content_type.split(";", maxsplit=1)[0].strip().lower()


def validate_pdf_metadata(file: UploadFile) -> None:
    if not file.filename:
        raise FileStorageError("Uploaded file name is required")

    if not file.filename.lower().endswith(PDF_EXTENSION):
        raise FileStorageError("Only PDF files are allowed")

    normalized_content_type = normalize_content_type(file.content_type)

    if normalized_content_type and normalized_content_type not in PDF_CONTENT_TYPES:
        raise FileStorageError("Only PDF files are allowed")


def validate_pdf_upload(
    file: UploadFile,
    content: bytes,
    max_upload_size_bytes: int,
) -> None:
    validate_pdf_metadata(file)

    if not content:
        raise FileStorageError("Uploaded file must not be empty")

    if len(content) > max_upload_size_bytes:
        raise UploadTooLargeError("Uploaded file exceeds maximum allowed size")

    if not content.startswith(PDF_SIGNATURE):
        raise FileStorageError("Uploaded file content is not a valid PDF")


def create_user_storage_key(user_id: str) -> str:
    if not user_id or not user_id.strip():
        raise FileStorageError("Authenticated user id is required")

    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()


def save_uploaded_pdf(
    *,
    file: UploadFile,
    upload_dir: str,
    user_id: str,
    statement_reference: str,
    content: bytes,
    max_upload_size_bytes: int,
) -> tuple[str, str]:
    """
    Save a PDF file using a generated file name.

    The original file name and raw user id are never trusted as path parts.
    """
    validate_pdf_upload(
        file=file,
        content=content,
        max_upload_size_bytes=max_upload_size_bytes,
    )

    upload_root = Path(upload_dir).resolve()
    user_storage_key = create_user_storage_key(user_id)
    user_upload_path = (upload_root / user_storage_key).resolve()

    if not user_upload_path.is_relative_to(upload_root):
        raise FileStorageError("Resolved upload path is outside upload directory")

    user_upload_path.mkdir(parents=True, exist_ok=True)

    stored_file_name = f"{statement_reference}-{uuid4().hex}.pdf"
    stored_file_path = user_upload_path / stored_file_name

    stored_file_path.write_bytes(content)

    return stored_file_name, str(stored_file_path)
