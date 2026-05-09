import time
from collections.abc import Callable

import requests


def wait_until_ready(
    check: Callable[[], bool],
    *,
    timeout_seconds: int = 60,
    delay_seconds: float = 1.0,
    failure_message: str = "Dependency was not ready in time",
) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            if check():
                return
        except Exception as error:
            last_error = error

        time.sleep(delay_seconds)

    if last_error:
        raise RuntimeError(f"{failure_message}: {last_error}") from last_error

    raise RuntimeError(failure_message)


def wait_for_http_ok(url: str) -> None:
    def check_http() -> bool:
        response = requests.get(url, timeout=2)
        return response.status_code == 200

    wait_until_ready(
        check_http,
        timeout_seconds=60,
        delay_seconds=1.0,
        failure_message=f"HTTP service was not ready: {url}",
    )
