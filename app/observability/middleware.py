import re
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from app.http import REQUEST_ID_HEADER, get_relative_url
from app.observability.context import bind_request_context, clear_request_context
from app.observability.logging import get_logger
from app.observability.metrics import record_app_exception
from app.problem_details import create_problem_response

REQUEST_ID_MAX_LENGTH = 128
METRICS_ROUTE_PATH = "/metrics"

_SAFE_REQUEST_ID_PATTERN = re.compile(
    rf"[A-Za-z0-9][A-Za-z0-9._-]{{0,{REQUEST_ID_MAX_LENGTH - 1}}}"
)

logger = get_logger(__name__)


def _resolve_request_id(candidate: str | None) -> str:
    if candidate is not None and _SAFE_REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate

    return str(uuid4())


def _should_log_request(path: str, metrics_path: str) -> bool:
    return path != metrics_path


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, metrics_path: str = METRICS_ROUTE_PATH) -> None:
        super().__init__(app)
        self.metrics_path = metrics_path

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = _resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        relative_url = get_relative_url(request)

        bind_request_context(request_id)

        started_at = perf_counter()
        try:
            response = await call_next(request)
        except Exception as error:
            duration_ms = round((perf_counter() - started_at) * 1000, 2)

            record_app_exception("unhandled")

            logger.error(
                "http.request",
                method=request.method,
                url=relative_url,
                status_code=500,
                duration_ms=duration_ms,
                exception_type=type(error).__name__,
            )

            return create_problem_response(
                request=request,
                status_code=500,
                detail="The request could not be completed.",
                request_id=request_id,
            )
        else:
            duration_ms = round((perf_counter() - started_at) * 1000, 2)

            response.headers[REQUEST_ID_HEADER] = request_id

            if _should_log_request(request.url.path, self.metrics_path):
                logger.info(
                    "http.request",
                    method=request.method,
                    url=relative_url,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                )

            return response
        finally:
            clear_request_context()
