import logging
import sys
from typing import Any

import structlog
from structlog.typing import EventDict

from app.observability.context import get_span_id, get_trace_id


def add_trace_context(
    _logger: object,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    trace_id = get_trace_id()
    span_id = get_span_id()

    if trace_id:
        event_dict["trace_id"] = trace_id

    if span_id:
        event_dict["span_id"] = span_id

    return event_dict


def remove_unsafe_exception_details(
    _logger: object,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Remove raw traceback inputs before JSON rendering.

    Application logs should use bounded exception categories and exception
    class names. Exception messages and tracebacks may contain credentials,
    file paths, statement data, or third-party payloads.
    """
    event_dict.pop("exc_info", None)
    event_dict.pop("stack_info", None)
    return event_dict


def configure_logging(log_level: str) -> None:
    level_name = log_level.upper()
    level_number = logging.getLevelNamesMapping().get(level_name, logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level_number,
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            add_trace_context,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            remove_unsafe_exception_details,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_number),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)
