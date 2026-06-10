from unittest.mock import Mock

from app.observability import context
from app.observability.context import (
    bind_request_context,
    clear_request_context,
    get_request_id,
    get_span_id,
    get_trace_id,
)


def test_request_context_round_trip():
    clear_request_context()
    bind_request_context("request-123")

    try:
        assert get_request_id() == "request-123"
    finally:
        clear_request_context()

    assert get_request_id() is None


def test_trace_and_span_ids_return_none_without_active_trace():
    assert get_trace_id() is None
    assert get_span_id() is None


def test_trace_and_span_ids_are_formatted_for_valid_span_context(monkeypatch):
    span_context = Mock(
        is_valid=True,
        trace_id=0x123,
        span_id=0x456,
    )
    span = Mock()
    span.get_span_context.return_value = span_context

    monkeypatch.setattr(
        context.trace,
        "get_current_span",
        lambda: span,
    )

    assert get_trace_id() == "00000000000000000000000000000123"
    assert get_span_id() == "0000000000000456"
