import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import Request
from starlette.routing import Match, Route

REQUEST_ID_HEADER = "X-Request-ID"
REDACTED_QUERY_VALUE = "[REDACTED]"
REDACTED_PATH = "/<redacted>"
UNMATCHED_ROUTE_PATH = "/<unmatched>"
MAX_QUERY_PARAMETERS = 20

_SAFE_QUERY_NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}")


def _safe_query_name(name: str) -> str:
    if _SAFE_QUERY_NAME_PATTERN.fullmatch(name):
        return name
    return "parameter"


def sanitize_query_string(query: str) -> str:
    """Preserve bounded, safe parameter names while redacting every value."""
    if not query:
        return ""

    try:
        pairs = parse_qsl(
            query,
            keep_blank_values=True,
            max_num_fields=MAX_QUERY_PARAMETERS,
        )
    except ValueError:
        return urlencode((("query", REDACTED_QUERY_VALUE),))

    redacted_pairs = [
        (_safe_query_name(name), REDACTED_QUERY_VALUE) for name, _value in pairs
    ]
    return urlencode(redacted_pairs, doseq=True)


def resolve_route_template(scope: Mapping[str, Any]) -> str | None:
    """Resolve a bounded Starlette/FastAPI route template without path values."""
    app = scope.get("app")
    partial_match: str | None = None

    for route in getattr(app, "routes", ()):
        if not isinstance(route, Route):
            continue

        match, _child_scope = route.matches(scope)
        route_path = getattr(route, "path", None)
        if not isinstance(route_path, str):
            continue

        if match is Match.FULL:
            return route_path
        if match is Match.PARTIAL:
            partial_match = route_path

    return partial_match


def get_safe_relative_url_from_scope(scope: Mapping[str, Any]) -> str:
    """Return a route template plus redacted query values for logs and errors."""
    path = resolve_route_template(scope) or UNMATCHED_ROUTE_PATH
    raw_query = scope.get("query_string", b"")
    query = (
        raw_query.decode("utf-8", errors="replace")
        if isinstance(raw_query, bytes)
        else str(raw_query)
    )
    sanitized_query = sanitize_query_string(query)

    if not sanitized_query:
        return path
    return f"{path}?{sanitized_query}"


def get_relative_url(request: Request) -> str:
    """Return the safe relative request URL used by logs and Problem Details."""
    return get_safe_relative_url_from_scope(request.scope)


def sanitize_url(url: str) -> str:
    """Return an outbound URL without credentials, path values, or query values."""
    parsed = urlsplit(url)
    hostname = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError:
        port = None
    netloc = f"{hostname}:{port}" if port is not None else hostname
    path = REDACTED_PATH if parsed.path and parsed.path != "/" else parsed.path or "/"

    return urlunsplit(
        (
            parsed.scheme,
            netloc,
            path,
            sanitize_query_string(parsed.query),
            "",
        )
    )
