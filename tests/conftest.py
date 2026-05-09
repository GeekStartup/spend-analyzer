import os

import pytest


def pytest_addoption(parser):
    """
    Add custom pytest command-line options.

    Default behavior:
        pytest
    Runs only fast/unit tests.

    Custom behavior:
        pytest --integration
    Runs only integration tests.

        pytest --all
    Runs all tests, including integration tests.
    """
    parser.addoption(
        "--integration",
        action="store_true",
        dest="run_integration_tests",
        default=False,
        help="Run only integration tests.",
    )

    parser.addoption(
        "--all",
        action="store_true",
        dest="run_all_tests",
        default=False,
        help="Run all tests, including integration tests.",
    )


def pytest_configure():
    """
    Configure required environment variables before test modules import the app.

    These values are used for both unit and integration tests.
    Unit tests mock DB calls.
    Integration tests use the Dockerized test stack.
    """
    os.environ["APP_NAME"] = "Spend Analyzer"
    os.environ["APP_ENV"] = "test"
    os.environ["APP_VERSION"] = "0.1.0"
    os.environ["APP_PORT"] = "8000"

    os.environ["DB_HOST"] = "localhost"
    os.environ["DB_PORT"] = "55432"
    os.environ["DB_NAME"] = "spend_analyzer_test"
    os.environ["DB_USER"] = "spend_user"
    os.environ["DB_PASSWORD"] = "change_me"

    os.environ["KEYCLOAK_ADMIN"] = "admin"
    os.environ["KEYCLOAK_ADMIN_PASSWORD"] = "change_me"

    os.environ["OIDC_ISSUER_URL"] = "http://localhost:58080/realms/spend-analyzer"
    os.environ["OIDC_JWKS_URL"] = (
        "http://localhost:58080/realms/spend-analyzer/protocol/openid-connect/certs"
    )
    os.environ["OIDC_AUDIENCE"] = "spend-analyzer-api"
    os.environ["OIDC_CLIENT_ID"] = "spend-analyzer-api"

    os.environ["OPENAI_API_KEY"] = ""
    os.environ["OPENAI_MODEL"] = "gpt-4.1-mini"

    os.environ["UPLOAD_DIR"] = "./uploads-test"
    os.environ["STORAGE_TYPE"] = "local"


def pytest_collection_modifyitems(config, items):
    """
    Control which tests run by default.

    Rules:
    - pytest                -> skip integration tests
    - pytest --integration  -> run only integration tests
    - pytest --all          -> run everything
    """
    run_integration_tests = config.getoption("run_integration_tests")
    run_all_tests = config.getoption("run_all_tests")

    if run_integration_tests and run_all_tests:
        raise pytest.UsageError("Use either --integration or --all, not both.")

    if run_all_tests:
        return

    skip_integration = pytest.mark.skip(
        reason="Integration test skipped by default. Use pytest --integration or pytest --all."
    )
    skip_non_integration = pytest.mark.skip(
        reason="Non-integration test skipped because pytest --integration was used."
    )

    for item in items:
        is_integration_test = item.get_closest_marker("integration") is not None

        if run_integration_tests:
            if not is_integration_test:
                item.add_marker(skip_non_integration)
        else:
            if is_integration_test:
                item.add_marker(skip_integration)
