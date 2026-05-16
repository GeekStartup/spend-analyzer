import os

import pytest


def pytest_addoption(parser):
    """
    Add custom pytest command-line options.

    Default behavior:
        pytest
    Runs all tests.

    Custom behavior:
        pytest --unit
    Runs only unit / non-integration tests.

        pytest --integration
    Runs only integration tests.
    """
    parser.addoption(
        "--unit",
        action="store_true",
        dest="run_unit_tests",
        default=False,
        help="Run only unit / non-integration tests.",
    )

    parser.addoption(
        "--integration",
        action="store_true",
        dest="run_integration_tests",
        default=False,
        help="Run only integration tests.",
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
    os.environ["OIDC_CLIENT_ID"] = "spend-analyzer-local"

    os.environ["OPENAI_API_KEY"] = ""
    os.environ["OPENAI_MODEL"] = "gpt-4.1-mini"

    os.environ["UPLOAD_DIR"] = "./uploads-test"
    os.environ["STORAGE_TYPE"] = "local"


def pytest_collection_modifyitems(config, items):
    """
    Control which tests run.

    Rules:
    - pytest                -> run all tests
    - pytest --unit         -> run only non-integration tests
    - pytest --integration  -> run only integration tests
    """
    run_unit_tests = config.getoption("run_unit_tests")
    run_integration_tests = config.getoption("run_integration_tests")

    if run_unit_tests and run_integration_tests:
        raise pytest.UsageError("Use either --unit or --integration, not both.")

    if not run_unit_tests and not run_integration_tests:
        return

    skip_integration = pytest.mark.skip(
        reason="Integration test skipped because pytest --unit was used."
    )
    skip_non_integration = pytest.mark.skip(
        reason="Non-integration test skipped because pytest --integration was used."
    )

    for item in items:
        is_integration_test = item.get_closest_marker("integration") is not None

        if run_unit_tests and is_integration_test:
            item.add_marker(skip_integration)

        if run_integration_tests and not is_integration_test:
            item.add_marker(skip_non_integration)
