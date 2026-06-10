from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.http import REQUEST_ID_HEADER, get_relative_url
from app.observability.context import get_request_id

PROBLEM_MEDIA_TYPE = "application/problem+json"
PROBLEM_INSTANCE_PREFIX = "urn:spend-analyzer:request:"
PROBLEM_TYPE_PREFIX = "urn:spend-analyzer:problem:"


@dataclass(frozen=True)
class ProblemDefinition:
    type: str
    title: str


DEFAULT_PROBLEMS = {
    400: ProblemDefinition(
        type=f"{PROBLEM_TYPE_PREFIX}invalid-request",
        title="Invalid request",
    ),
    401: ProblemDefinition(
        type=f"{PROBLEM_TYPE_PREFIX}invalid-credentials",
        title="Authentication failed",
    ),
    403: ProblemDefinition(
        type=f"{PROBLEM_TYPE_PREFIX}forbidden",
        title="Access forbidden",
    ),
    404: ProblemDefinition(
        type=f"{PROBLEM_TYPE_PREFIX}not-found",
        title="Resource not found",
    ),
    405: ProblemDefinition(
        type=f"{PROBLEM_TYPE_PREFIX}method-not-allowed",
        title="Method not allowed",
    ),
    413: ProblemDefinition(
        type=f"{PROBLEM_TYPE_PREFIX}upload-too-large",
        title="Upload too large",
    ),
    422: ProblemDefinition(
        type=f"{PROBLEM_TYPE_PREFIX}request-validation",
        title="Request validation failed",
    ),
    500: ProblemDefinition(
        type=f"{PROBLEM_TYPE_PREFIX}internal-server-error",
        title="Internal server error",
    ),
    503: ProblemDefinition(
        type=f"{PROBLEM_TYPE_PREFIX}service-unavailable",
        title="Service unavailable",
    ),
}


class ProblemException(HTTPException):
    """HTTP exception carrying an explicit RFC 9457 problem definition."""

    def __init__(
        self,
        *,
        status_code: int,
        type: str,
        title: str,
        detail: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers=dict(headers) if headers is not None else None,
        )
        self.problem_type = type
        self.problem_title = title


def _resolve_request_id() -> str:
    return get_request_id() or str(uuid4())


def _problem_definition(status_code: int) -> ProblemDefinition:
    return DEFAULT_PROBLEMS.get(
        status_code,
        ProblemDefinition(type="about:blank", title="HTTP error"),
    )


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
    resolved_request_id = request_id or _resolve_request_id()
    definition = _problem_definition(status_code)

    content: dict[str, Any] = {
        "type": type or definition.type,
        "title": title or definition.title,
        "status": status_code,
        "detail": detail,
        "instance": f"{PROBLEM_INSTANCE_PREFIX}{resolved_request_id}",
        "request_id": resolved_request_id,
        "url": get_relative_url(request),
    }

    if extensions:
        content.update(extensions)

    response_headers = dict(headers or {})
    response_headers[REQUEST_ID_HEADER] = resolved_request_id

    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=response_headers,
        media_type=PROBLEM_MEDIA_TYPE,
    )


def _safe_http_detail(exception: StarletteHTTPException) -> str:
    if isinstance(exception.detail, str):
        return exception.detail

    return _problem_definition(exception.status_code).title


async def http_exception_handler(
    request: Request,
    exception: StarletteHTTPException,
) -> JSONResponse:
    problem_type = None
    problem_title = None

    if isinstance(exception, ProblemException):
        problem_type = exception.problem_type
        problem_title = exception.problem_title

    return create_problem_response(
        request=request,
        status_code=exception.status_code,
        detail=_safe_http_detail(exception),
        type=problem_type,
        title=problem_title,
        headers=exception.headers,
    )


def _sanitized_validation_errors(
    exception: RequestValidationError,
) -> list[dict[str, Any]]:
    return [
        {
            "code": error["type"],
            "location": list(error["loc"]),
            "message": error["msg"],
        }
        for error in exception.errors()
    ]


async def request_validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    return create_problem_response(
        request=request,
        status_code=422,
        detail="One or more request fields are invalid.",
        extensions={"errors": _sanitized_validation_errors(exception)},
    )


def register_problem_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(
        RequestValidationError,
        request_validation_exception_handler,
    )
