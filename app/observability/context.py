from opentelemetry import trace
from structlog.contextvars import bind_contextvars, clear_contextvars, get_contextvars


def bind_request_context(request_id: str, url: str | None = None) -> None:
    context: dict[str, str] = {"request_id": request_id}

    if url is not None:
        context["url"] = url

    bind_contextvars(**context)


def clear_request_context() -> None:
    clear_contextvars()


def get_request_id() -> str | None:
    value = get_contextvars().get("request_id")

    if isinstance(value, str):
        return value

    return None


def get_request_url() -> str | None:
    value = get_contextvars().get("url")

    if isinstance(value, str):
        return value

    return None


def get_trace_id() -> str | None:
    span_context = trace.get_current_span().get_span_context()

    if not span_context.is_valid:
        return None

    return f"{span_context.trace_id:032x}"


def get_span_id() -> str | None:
    span_context = trace.get_current_span().get_span_context()

    if not span_context.is_valid:
        return None

    return f"{span_context.span_id:016x}"
