from io import BytesIO
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import get_current_user
from app.config import settings
from app.errors import (
    FileStorageError,
    FileStorageUnavailableError,
    InvalidPdfError,
    UploadTooLargeError,
)
from app.observability.logging import get_logger
from app.observability.metrics import (
    record_file_storage_failure,
    record_statement_ingestion_attempt,
    record_statement_ingestion_failure,
    record_statement_ingestion_success,
)
from app.schemas.auth_schema import AuthenticatedUser
from app.schemas.ingest_schema import StatementUploadResponse
from app.services.file_storage_service import (
    PDF_CONTENT_TYPES,
    normalize_content_type,
    save_uploaded_pdf,
    validate_pdf_metadata,
)

CHUNK_SIZE_BYTES = 1024 * 1024

INGESTION_FAILURE_INVALID_PDF = "invalid_pdf"
INGESTION_FAILURE_UPLOAD_TOO_LARGE = "upload_too_large"
INGESTION_FAILURE_STORAGE_UNAVAILABLE = "storage_unavailable"
INGESTION_FAILURE_STORAGE_INTERNAL_ERROR = "storage_internal_error"

STORAGE_FAILURE_UNAVAILABLE = "unavailable"
STORAGE_FAILURE_INTERNAL_ERROR = "internal_error"

OBSERVABILITY_CONTENT_TYPE_UNKNOWN = "unknown"

router = APIRouter(tags=["Ingestion"])
logger = get_logger(__name__)


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    stripped_value = value.strip()

    if not stripped_value:
        return None

    return stripped_value


def get_observability_content_type(content_type: str | None) -> str:
    normalized_content_type = normalize_content_type(content_type)

    if normalized_content_type in PDF_CONTENT_TYPES:
        return normalized_content_type

    return OBSERVABILITY_CONTENT_TYPE_UNKNOWN


async def read_upload_file_with_limit(
    file: UploadFile,
    max_upload_size_bytes: int,
) -> bytes:
    content = BytesIO()
    total_size = 0

    while True:
        chunk = await file.read(CHUNK_SIZE_BYTES)

        if not chunk:
            break

        total_size += len(chunk)

        if total_size > max_upload_size_bytes:
            raise UploadTooLargeError("Uploaded file exceeds maximum allowed size")

        content.write(chunk)

    return content.getvalue()


def _add_ingestion_failure_context(
    error: FileStorageError,
    *,
    statement_reference: str,
    stage: str,
    failure_category: str,
) -> None:
    error.add_context(
        operation="statement_ingestion",
        stage=stage,
        statement_reference=statement_reference,
        failure_category=failure_category,
    )


@router.post(
    "/ingest",
    response_model=StatementUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_statement(
    file: Annotated[UploadFile, File()],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    institution: Annotated[str | None, Form()] = None,
    account_type: Annotated[str | None, Form()] = None,
    account_name: Annotated[str | None, Form()] = None,
    statement_format: Annotated[str | None, Form()] = None,
) -> StatementUploadResponse:
    statement_reference = str(uuid4())
    content_type = get_observability_content_type(file.content_type)

    record_statement_ingestion_attempt()

    try:
        validate_pdf_metadata(file)
        content = await read_upload_file_with_limit(
            file=file,
            max_upload_size_bytes=settings.max_upload_size_bytes,
        )
        logger.debug(
            "Statement upload content read",
            statement_reference=statement_reference,
            file_size_bytes=len(content),
        )

        stored_file_name, _stored_file_path = await run_in_threadpool(
            save_uploaded_pdf,
            file=file,
            upload_dir=settings.upload_dir,
            user_id=current_user.user_id,
            statement_reference=statement_reference,
            content=content,
            max_upload_size_bytes=settings.max_upload_size_bytes,
        )
    except UploadTooLargeError as error:
        record_statement_ingestion_failure(INGESTION_FAILURE_UPLOAD_TOO_LARGE)
        _add_ingestion_failure_context(
            error,
            statement_reference=statement_reference,
            stage="upload",
            failure_category=INGESTION_FAILURE_UPLOAD_TOO_LARGE,
        )
        error.add_context(
            configured_max_size_bytes=settings.max_upload_size_bytes,
        )
        raise
    except InvalidPdfError as error:
        record_statement_ingestion_failure(INGESTION_FAILURE_INVALID_PDF)
        _add_ingestion_failure_context(
            error,
            statement_reference=statement_reference,
            stage="validation",
            failure_category=INGESTION_FAILURE_INVALID_PDF,
        )
        raise
    except FileStorageUnavailableError as error:
        record_file_storage_failure(STORAGE_FAILURE_UNAVAILABLE)
        record_statement_ingestion_failure(INGESTION_FAILURE_STORAGE_UNAVAILABLE)
        _add_ingestion_failure_context(
            error,
            statement_reference=statement_reference,
            stage="storage",
            failure_category=INGESTION_FAILURE_STORAGE_UNAVAILABLE,
        )
        raise
    except FileStorageError as error:
        record_file_storage_failure(STORAGE_FAILURE_INTERNAL_ERROR)
        record_statement_ingestion_failure(INGESTION_FAILURE_STORAGE_INTERNAL_ERROR)
        _add_ingestion_failure_context(
            error,
            statement_reference=statement_reference,
            stage="storage",
            failure_category=INGESTION_FAILURE_STORAGE_INTERNAL_ERROR,
        )
        raise

    file_size_bytes = len(content)
    record_statement_ingestion_success(
        content_type=content_type,
        file_size_bytes=file_size_bytes,
    )

    logger.info(
        "Statement ingestion succeeded",
        statement_reference=statement_reference,
        content_type=content_type,
        file_size_bytes=file_size_bytes,
    )

    return StatementUploadResponse(
        statement_reference=statement_reference,
        original_file_name=file.filename or "",
        stored_file_name=stored_file_name,
        content_type=file.content_type or "",
        file_size_bytes=file_size_bytes,
        status="UPLOADED",
        institution=normalize_optional_text(institution),
        account_type=normalize_optional_text(account_type),
        account_name=normalize_optional_text(account_name),
        statement_format=normalize_optional_text(statement_format),
    )
