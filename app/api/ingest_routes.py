from io import BytesIO
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from opentelemetry.trace import Span, Status, StatusCode
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import get_current_user
from app.config import settings
from app.observability.logging import get_logger
from app.observability.metrics import (
    record_statement_ingestion_attempt,
    record_statement_ingestion_failure,
    record_statement_ingestion_success,
)
from app.observability.tracing import start_span
from app.schemas.auth_schema import AuthenticatedUser
from app.schemas.ingest_schema import StatementUploadResponse
from app.services.file_storage_service import (
    FileStorageError,
    UploadTooLargeError,
    normalize_content_type,
    save_uploaded_pdf,
    validate_pdf_metadata,
)

CHUNK_SIZE_BYTES = 1024 * 1024

INGESTION_FAILURE_UPLOAD_TOO_LARGE = "upload_too_large"
INGESTION_FAILURE_FILE_VALIDATION_OR_STORAGE = "file_validation_or_storage"

router = APIRouter(tags=["Ingestion"])
logger = get_logger(__name__)


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    stripped_value = value.strip()

    if not stripped_value:
        return None

    return stripped_value


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


def record_ingestion_failure(
    *,
    span: Span,
    statement_reference: str,
    failure_category: str,
    error: FileStorageError,
) -> None:
    """
    Record one failed statement-ingestion outcome.

    Failure categories must remain bounded because they are used as
    Prometheus metric labels. Exception messages, filenames, user IDs,
    and financial metadata must not be recorded.
    """
    record_statement_ingestion_failure(failure_category)

    span.record_exception(error)
    span.set_status(
        Status(
            status_code=StatusCode.ERROR,
            description=failure_category,
        )
    )
    span.set_attribute("app.outcome", "failed")
    span.set_attribute(
        "app.failure.category",
        failure_category,
    )

    logger.warning(
        "statement.ingestion",
        outcome="failed",
        statement_reference=statement_reference,
        failure_category=failure_category,
        exception_type=error.__class__.__name__,
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
    content_type = normalize_content_type(file.content_type) or "unknown"

    record_statement_ingestion_attempt()

    with start_span(
        "statement.ingestion",
        attributes={
            "app.statement.reference": statement_reference,
            "app.statement.content_type": content_type,
        },
    ) as span:
        try:
            validate_pdf_metadata(file)

            content = await read_upload_file_with_limit(
                file=file,
                max_upload_size_bytes=settings.max_upload_size_bytes,
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
            record_ingestion_failure(
                span=span,
                statement_reference=statement_reference,
                failure_category=INGESTION_FAILURE_UPLOAD_TOO_LARGE,
                error=error,
            )

            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=str(error),
            ) from error
        except FileStorageError as error:
            record_ingestion_failure(
                span=span,
                statement_reference=statement_reference,
                failure_category=(INGESTION_FAILURE_FILE_VALIDATION_OR_STORAGE),
                error=error,
            )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error

        file_size_bytes = len(content)

        record_statement_ingestion_success(
            content_type=content_type,
            file_size_bytes=file_size_bytes,
        )

        span.set_attribute("app.outcome", "succeeded")
        span.set_attribute(
            "app.statement.file_size_bytes",
            file_size_bytes,
        )

        logger.info(
            "statement.ingestion",
            outcome="succeeded",
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
