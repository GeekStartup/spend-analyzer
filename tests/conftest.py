import os


def pytest_configure():
    """
    Configure required environment variables before test modules import the app.

    These values are used for both unit and integration tests.
    Unit tests mock DB calls.
    Integration tests use the test PostgreSQL container.
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
