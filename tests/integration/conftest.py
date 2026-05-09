import shutil

import pytest

from tests.support.docker_compose import start_integration_stack, stop_integration_stack
from tests.support.readiness import wait_for_http_ok


@pytest.fixture(scope="session", autouse=True)
def integration_environment():
    """
    Start and validate all external services needed by integration tests.

    This starts the real Dockerized app and its test dependencies.
    """
    if not shutil.which("docker"):
        pytest.skip("Docker is required for integration tests")

    start_integration_stack()

    try:
        wait_for_http_ok("http://localhost:18000/health")
        yield
    finally:
        stop_integration_stack()
