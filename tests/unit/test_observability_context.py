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
