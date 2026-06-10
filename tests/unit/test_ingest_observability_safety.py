import pytest

from app.api.ingest_routes import get_observability_content_type


@pytest.mark.parametrize(
    ("content_type", "expected"),
    [
        ("application/pdf", "application/pdf"),
        ("Application/PDF; charset=binary", "application/pdf"),
        ("application/x-pdf", "application/x-pdf"),
        ("text/plain", "unknown"),
        ("arbitrary/client-controlled-value", "unknown"),
        (None, "unknown"),
    ],
)
def test_get_observability_content_type_returns_bounded_category(
    content_type,
    expected,
):
    assert get_observability_content_type(content_type) == expected
