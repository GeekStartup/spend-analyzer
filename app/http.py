from fastapi import Request

REQUEST_ID_HEADER = "X-Request-ID"


def get_relative_url(request: Request) -> str:
    """Return the request path and optional query string without host details."""
    path = request.url.path
    query = request.url.query

    if not query:
        return path

    return f"{path}?{query}"
