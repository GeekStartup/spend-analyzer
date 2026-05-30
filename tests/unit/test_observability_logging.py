from app.observability import logging as observability_logging


def test_add_trace_context_adds_available_trace_context(monkeypatch):
    monkeypatch.setattr(
        observability_logging,
        "get_trace_id",
        lambda: "trace-123",
    )
    monkeypatch.setattr(
        observability_logging,
        "get_span_id",
        lambda: "span-123",
    )

    event = observability_logging.add_trace_context(
        _logger=object(),
        _method_name="info",
        event_dict={"event": "test.event"},
    )

    assert event == {
        "event": "test.event",
        "trace_id": "trace-123",
        "span_id": "span-123",
    }


def test_add_trace_context_skips_missing_trace_context(monkeypatch):
    monkeypatch.setattr(observability_logging, "get_trace_id", lambda: None)
    monkeypatch.setattr(observability_logging, "get_span_id", lambda: None)

    event = observability_logging.add_trace_context(
        _logger=object(),
        _method_name="info",
        event_dict={"event": "test.event"},
    )

    assert event == {"event": "test.event"}


def test_configure_logging_and_get_logger():
    observability_logging.configure_logging("INFO")

    logger = observability_logging.get_logger("test.logger")

    assert logger is not None
