import re
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from app.http import REQUEST_ID_HEADER, get_relative_url
from app.observability.context import bind_request_context, clear_request_context
from app.observability.logging import get_logger
from app.problem_details import handle_unexpected_exception

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


def _log_http_request(
    *,
    method: str,
    status_code: int,
    duration_ms: float,
) -> None:
    log = logger.error if status_code >= 400 else logger.info
    log(
        "http.request",
        method=method,
        status_code=status_code,
        duration_ms=duration_ms,
    )


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
        request.state.request_id = request_id
        request.state.url = relative_url

        bind_request_context(request_id, relative_url)
        should_log = _should_log_request(request.url.path, self.metrics_path)
        started_at = perf_counter()

        try:
            response = await call_next(request)
        except Exception as error:
            response = await handle_unexpected_exception(request, error)
            response.headers[REQUEST_ID_HEADER] = request_id

            if should_log:
                _log_http_request(
                    method=request.method,
                    status_code=500,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                )

            return response
        else:
            response.headers[REQUEST_ID_HEADER] = request_id

            if should_log:
                _log_http_request(
                    method=request.method,
                    status_code=response.status_code,
                    duration_ms=round((perf_counter() - started_at) * 1000, 2),
                )

            return response
        finally:
            clear_request_context()
