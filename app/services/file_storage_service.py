from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}
PDF_EXTENSION = ".pdf"
PDF_SIGNATURE = b"%PDF"
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


class FileStorageError(Exception):
    """
    Raised when uploaded file validation or storage fails.
    """


def validate_pdf_upload(file: UploadFile, content: bytes) -> None:
    if not file.filename:
        raise FileStorageError("Uploaded file name is required")

    if not file.filename.lower().endswith(PDF_EXTENSION):
        raise FileStorageError("Only PDF files are allowed")

    if file.content_type not in PDF_CONTENT_TYPES:
        raise FileStorageError("Only PDF files are allowed")

    if not content:
        raise FileStorageError("Uploaded file must not be empty")

    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise FileStorageError("Uploaded file exceeds maximum allowed size")

    if not content.startswith(PDF_SIGNATURE):
        raise FileStorageError("Uploaded file content is not a valid PDF")


def save_uploaded_pdf(
    *,
    file: UploadFile,
    upload_dir: str,
    user_id: str,
    statement_reference: str,
    content: bytes,
) -> tuple[str, str]:
    """
    Save a PDF file using a generated file name.

    The original file name is never trusted as the stored file name.
    """
    validate_pdf_upload(file, content)
    user_upload_path = Path(upload_dir) / user_id
    user_upload_path.mkdir(parents=True, exist_ok=True)

    stored_file_name = f"{statement_reference}-{uuid4().hex}.pdf"
    stored_file_path = user_upload_path / stored_file_name

    stored_file_path.write_bytes(content)

    return stored_file_name, str(stored_file_path)
