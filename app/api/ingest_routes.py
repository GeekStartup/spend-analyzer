from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import get_current_user
from app.config import settings
from app.schemas.auth_schema import AuthenticatedUser
from app.schemas.ingest_schema import StatementUploadResponse
from app.services.file_storage_service import FileStorageError, save_uploaded_pdf


CHUNK_SIZE_BYTES = 1024 * 1024

router = APIRouter(tags=["Ingestion"])


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
    chunks: list[bytes] = []
    total_size = 0

    while True:
        chunk = await file.read(CHUNK_SIZE_BYTES)

        if not chunk:
            break

        total_size += len(chunk)

        if total_size > max_upload_size_bytes:
            raise FileStorageError("Uploaded file exceeds maximum allowed size")

        chunks.append(chunk)

    return b"".join(chunks)


@router.post(
    "/ingest",
    response_model=StatementUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_statement(
    file: UploadFile = File(...),
    institution: str | None = Form(default=None),
    account_type: str | None = Form(default=None),
    account_name: str | None = Form(default=None),
    statement_format: str | None = Form(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> StatementUploadResponse:
    statement_reference = str(uuid4())

    try:
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
    except FileStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return StatementUploadResponse(
        statement_reference=statement_reference,
        original_file_name=file.filename or "",
        stored_file_name=stored_file_name,
        content_type=file.content_type or "",
        file_size_bytes=len(content),
        status="UPLOADED",
        institution=normalize_optional_text(institution),
        account_type=normalize_optional_text(account_type),
        account_name=normalize_optional_text(account_name),
        statement_format=normalize_optional_text(statement_format),
    )
