from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from app.observability.context import bind_request_context, clear_request_context
from app.observability.logging import get_logger
from app.observability.metrics import record_app_exception

REQUEST_ID_HEADER = "X-Request-ID"
METRICS_ROUTE_PATH = "/metrics"

logger = get_logger(__name__)


def _get_route_path(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)

    if isinstance(path, str):
        return path

    return "unmatched"


def _should_log_request(route_path: str, metrics_path: str) -> bool:
    return route_path != metrics_path


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, metrics_path: str = METRICS_ROUTE_PATH) -> None:
        super().__init__(app)
        self.metrics_path = metrics_path

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER)

        if not request_id:
            request_id = str(uuid4())

        bind_request_context(request_id)

        started_at = perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            route_path = _get_route_path(request)

            record_app_exception("unhandled")

            logger.exception(
                "http.request",
                method=request.method,
                route=route_path,
                status_code=500,
                duration_ms=duration_ms,
                exception_type=type(exc).__name__,
            )

            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error"},
                headers={REQUEST_ID_HEADER: request_id},
            )
        else:
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            route_path = _get_route_path(request)

            response.headers[REQUEST_ID_HEADER] = request_id

            if _should_log_request(route_path, self.metrics_path):
                logger.info(
                    "http.request",
                    method=request.method,
                    route=route_path,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                )

            return response
        finally:
            clear_request_context()
