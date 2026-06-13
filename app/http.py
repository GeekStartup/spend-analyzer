from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import Request

REQUEST_ID_HEADER = "X-Request-ID"
REDACTED_QUERY_VALUE = "[REDACTED]"


def sanitize_query_string(query: str) -> str:
    """Preserve query parameter names while redacting every value."""
    if not query:
        return ""

    redacted_pairs = [
        (name, REDACTED_QUERY_VALUE)
        for name, _value in parse_qsl(query, keep_blank_values=True)
    ]
    return urlencode(redacted_pairs, doseq=True)


def sanitize_url(url: str) -> str:
    """Return a URL without a fragment and with all query values redacted."""
    parsed = urlsplit(url)
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            sanitize_query_string(parsed.query),
            "",
        )
    )


def get_relative_url(request: Request) -> str:
    """Return the request path and sanitized query string without host details."""
    path = request.url.path
    query = sanitize_query_string(request.url.query)

    if not query:
        return path

    return f"{path}?{query}"
