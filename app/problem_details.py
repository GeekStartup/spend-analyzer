import traceback
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import (
    ApplicationError,
    AuthenticationRequiredError,
    DatabaseUnavailableError,
    FileStorageError,
    FileStorageUnavailableError,
    IdentityProviderUnavailableError,
    InvalidCredentialsError,
    InvalidPdfError,
    UploadTooLargeError,
)
from app.http import REQUEST_ID_HEADER, get_relative_url
from app.observability.context import bind_request_context, get_request_id
from app.observability.logging import get_logger
from app.observability.metrics import record_app_exception

PROBLEM_MEDIA_TYPE = "application/problem+json"
PROBLEM_INSTANCE_PREFIX = "urn:spend-analyzer:request:"
PROBLEM_TYPE_PREFIX = "urn:spend-analyer:problem:"

logger = get_logger(__name__)

@dataclass(frozen=True)
class ProblemDefinition:
    status_code: int
    type: str
    title: str
    log_message: str
    detail: str
    headers: Mapping[str, str] | None = None

DEFAULT_PROBLEMS = {
    400: ProblemDefinition(
        status_code=400,
        type=f"{PROBLEM_TYPE_PREFIX}invalid-request",
        title="Invalid request",
        log_message="HTTP request rejected",
        detail="The request is invalid.",
    ),
    401: ProblemDefinition(
        status_code=401,
        type=f"{PROBLEM_TYPE_PREFIX}invalid-credentials",
        title="Authentication failed",
        log_message="HTTP request rejected",
        detail="Valid bearer credentials are required.",
    ),
    403: ProblemDefinition(
        status_code=403,
        type=f"{PROBLEM_TYPE_PREFIX}forbidden",
        title="Access forbidden",
        log_message="HTTP request rejected",
        detail="Access to this resource is forbidden.",
    ),
    404: ProblemDefinition(
        status_code=404,
        type=f"{PROBLEM_TYPE_PREFIX}not-found",
        title="Resource not found",
        log_message="HTTP request rejected",
        detail="The requested resource was not found.",
    ),
    405: ProblemDefinition(
        status_code=405,
        type=f"{PROBLEM_TYPE_PREFIX}method-not-allowed",
        title="Method not allowed",
        log_message="HTTP request rejected",
        detail="The request method is not allowed for this resource.",
    ),
    413: ProblemDefinition(
        status_code=413,
        type=f"{PROBLEM_TYPE_PREFIX}upload-too-large",
        title="Upload too large",
        log_message="HTTP request rejected",
        detail="The uploaded file exceeds the maximum allowed size.",
    ),
    422: ProblemDefinition(
        status_code=422,
        type=f"{PROBLEM_TYPE_PREFIX}request-validation",
        title="Request validation failed",
        log_message="Request validation failed",
        detail="One or more request fields are invalid.",
    ),
    500: ProblemDefinition(
        status_code=500,
        type=f"{PROBLEM_TYPE_PREFIX}internal-server-error",
        title="Internal server error",
        log_message="Unhandled application exception",
        detail="Something went wrong. Please try again later.",
    ),
    503: ProblemDefinition(
        status_code=503,
        type=f"{PROBLEM_TYPE_PREFIX}service-unavailable",
        title="Service unavailable",
        log_message="Required service is unavailable",
        detail="A required service is temporarily unavailable.",
    ),
}

APPLICATION_PROBLEMS: dict[type[ApplicationError], ProblemDefinition] = {
    AuthenticationRequiredError: ProblemDefinition(
        status_code=401,
        type=f"{PROBLEM_TYPE_PREFIX}authentication-required",
        title="Authentication required",
        log_message="Authentication failed because credentials were missing",
        detail="Valid bearer credentials are required.",
        headers={"WWW-Authenticate": "Bearer"},
    ),
    InvalidCredentialsError: ProblemDefinition(
        status_code=401,
        type=f"{PROBLEM_TYPE_PREFIX}invalid-credentials",
        title="Authentication failed",
        log_message="Authentication failed because credentials were invalid",
        detail="Valid bearer credentials are required.",
        headers={"WWW-Authenticate": "Bearer"},
    ),
    DatabaseUnavailableError: ProblemDefinition(
        status_code=503,
        type=f"{PROBLEM_TYPE_PREFIX}database-unavailable",
        title="Database unavailable",
        log_message="Database health check failed",
        detail="The database health check could not be completed.",
    ),
    IdentityProviderUnavailableError: ProblemDefinition(
        status_code=503,
        type=f"{PROBLEM_TYPE_PREFIX}identity-provider-unavailable",
        title="Identity provider unavailable",
        log_message="Identity provider operation failed",
        detail="Authentication could not be completed. Try again later.",
    ),
    InvalidPdfError: ProblemDefinition(
        status_code=400,
        type=f"{PROBLEM_TYPE_PREFIX}invalid-pdf",
        title="Invalid PDF",
        log_message="Statement ingestion rejected an invalid PDF",
        detail="The uploaded file is not a valid PDF.",
    ),
    UploadTooLargeError: ProblemDefinition(
        status_code=413,
        type=f"{PROBLEM_TYPE_PREFIX}upload-too-large",
        title="Upload too large",
        log_message="Statement ingestion rejected an oversized upload",
        detail="The uploaded file exceeds the maximum allowed size.",
    ),
    FileStorageUnavailableError: ProblemDefinition(
        status_code=503,
        type=f"{PROBLEM_TYPE_PREFIX}file-storage-unavailable",
        title="File storage unavailable",
        log_message="Statement ingestion failed because file storage is unavailable",
        detail="The uploaded statement could not be stored. Try again later.",
    ),
    FileStorageError: ProblemDefinition(
        status_code=500,
        type=f"{PROBLEM_TYPE_PREFIX}internal-server-error",
        title="Internal server error",
        log_message="Statement ingestion failed because of an unexpected storage error",
        detail="Something went wrong. Please try again later.",
    ),
    ApplicationError: DEFAULT_PROBLEMS[500],
}

_SAFE_APPLICATION_CONTEXT_FIELDS = {
    "cause_type",
    "configured_max_size_bytes",
    "count",
    "dependency",
    "failure_category",
    "file_size_bytes",
    "operation",
    "stage",
    "statement_reference",
    "timeout_seconds",
}
_SAFE_CONTEXT_VALUE_TYPES = (str, int, float, bool)
_VALIDATION_MESSAGES = {
    "missing": "Field is required.",
    "extra_forbidden": "Unexpected field.",
    "greater_than": "Value is too small.",
    "greater_than_equal": "Value is too small.",
    "less_than": "Value is too large.",
    "less_than_equal": "Value is too large.",
    "string_too_short": "Value is too short.",
    "string_too_long": "Value is too long.",
}


def _request_context(request: Request) -> tuple[str, str]:
    request_id = getattr(request.state, "request_id", None)
    if not isinstance(request_id, str):
        request_id = get_request_id() or str(uuid4())

    url = getattr(request.state, "url", None)
    if not isinstance(url, str):
        url = get_relative_url(request)

    return request_id, url


def _ensure_request_context(request: Request) -> None:
    request_id, url = _request_context(request)
    bind_request_context(request_id, url)


def _problem_definition(status_code: int) -> ProblemDefinition:
    return DEFAULT_PROBLEMS.get(
        status_code,
        ProblemDefinition(
            status_code=status_code,
            type="about:blank",
            title="HTTP error",
            log_message="HTTP request rejected",
            detail="The request could not be completed.",
        ),
    )


def _application_problem(exception: ApplicationError) -> ProblemDefinition:
    for exception_type in type(exception).__mro__:
        definition = APPLICATION_PROBLEMS.get(exception_type)
        if definition is not None:
            return definition

    return APPLICATION_PROBLEMS[ApplicationError]


def _safe_application_context(exception: ApplicationError) -> dict[str, object]:
    return {
        key: value
        for key, value in exception.context.items()
        if key in _SAFE_APPLICATION_CONTEXT_FIELDS
        and isinstance(value, _SAFE_CONTEXT_VALUE_TYPES)
    }


def _safe_stack_frames(exception: Exception) -> list[dict[str, object]]:
    frames: list[dict[str, object]] = []

    for frame in traceback.extract_tb(exception.__traceback__):
        parts = frame.filename.replace("\\", "/").split("/")
        if "app" not in parts:
            continue

        app_index = len(parts) - 1 - parts[::-1].index("app")
        module_parts = parts[app_index:]
        module_parts[-1] = module_parts[-1].removesuffix(".py")
        frames.append(
            {
                "module": ".".join(module_parts),
                "function": frame.name,
                "line": frame.lineno,
            }
        )

    return frames[-8:]


def create_problem_response(
    *,
    request: Request,
    status_code: int,
    detail: str,
    type: str | None = None,
    title: str | None = None,
    headers: Mapping[str, str] | None = None,
    extensions: Mapping[str, Any] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    resolved_request_id, url = _request_context(request)
    if request_id is not None:
        resolved_request_id = request_id

    definition = _problem_definition(status_code)
    content: dict[str, Any] = {
        "type": type or definition.type,
        "title": title or definition.title,
        "status": status_code,
        "detail": detail,
        "instance": f"{PROBLEM_INSTANCE_PREFIX}{resolved_request_id}",
        "request_id": resolved_request_id,
        "url": url,
    }

    if extensions:
        for key, value in extensions.items():
            if key not in content:
                content[key] = value

    response_headers = dict(headers or {})
    response_headers[REQUEST_ID_HEADER] = resolved_request_id

    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=response_headers,
        media_type=PROBLEM_MEDIA_TYPE,
    )


def _safe_http_detail(exception: StarletteHTTPException) -> str:
    return _problem_definition(exception.status_code).detail


async def http_exception_handler(
    request: Request,
    exception: StarletteHTTPException,
) -> JSONResponse:
    _ensure_request_context(request)
    definition = _problem_definition(exception.status_code)
    logger.error(
        definition.log_message,
        status_code=exception.status_code,
        problem_type=definition.type,
        exception_type=exception.__class__.__name__,
    )

    return create_problem_response(
        request=request,
        status_code=exception.status_code,
        detail=_safe_http_detail(exception),
        type=definition.type,
        title=definition.title,
        headers=exception.headers,
    )


def _validation_message(error_type: str) -> str:
    return _VALIDATION_MESSAGES.get(error_type, "Invalid value.")


def _sanitized_validation_errors(
    exception: RequestValidationError,
) -> list[dict[str, Any]]:
    return [
        {
            "code": error["type"],
            "location": list(error["loc"]),
            "message": _validation_message(error["type"]),
        }
        for error in exception.errors()
    ]


async def request_validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    _ensure_request_context(request)
    definition = DEFAULT_PROBLEMS[422]
    errors = _sanitized_validation_errors(exception)
    logger.error(
        definition.log_message,
        status_code=definition.status_code,
        problem_type=definition.type,
        exception_type=exception.__class__.__name__,
        error_count=len(errors),
    )

    return create_problem_response(
        request=request,
        status_code=definition.status_code,
        detail=definition.detail,
        type=definition.type,
        title=definition.title,
        extensions={"errors": errors},
    )


async def application_exception_handler(
    request: Request,
    exception: ApplicationError,
) -> JSONResponse:
    _ensure_request_context(request)
    definition = _application_problem(exception)
    logger.error(
        definition.log_message,
        **_safe_application_context(exception),
        status_code=definition.status_code,
        problem_type=definition.type,
        exception_type=exception.__class__.__name__,
    )

    return create_problem_response(
        request=request,
        status_code=definition.status_code,
        detail=definition.detail,
        type=definition.type,
        title=definition.title,
        headers=definition.headers,
    )


async def handle_unexpected_exception(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    _ensure_request_context(request)
    definition = DEFAULT_PROBLEMS[500]
    record_app_exception("unhandled")
    logger.error(
        definition.log_message,
        status_code=definition.status_code,
        problem_type=definition.type,
        exception_type=exception.__class__.__name__,
        exception_module=exception.__class__.__module__,
        stack_frames=_safe_stack_frames(exception),
    )

    return create_problem_response(
        request=request,
        status_code=definition.status_code,
        detail=definition.detail,
        type=definition.type,
        title=definition.title,
    )


async def unexpected_exception_handler(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    return await handle_unexpected_exception(request, exception)


def register_problem_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(
        RequestValidationError,
        request_validation_exception_handler,
    )
    app.add_exception_handler(ApplicationError, application_exception_handler)
    app.add_exception_handler(Exception, unexpected_exception_handler)
