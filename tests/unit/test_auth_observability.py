from app.auth import dependencies


def test_auth_failure_categories_are_bounded():
    assert dependencies.AUTH_FAILURE_MISSING_CREDENTIALS == "missing_credentials"
    assert dependencies.AUTH_FAILURE_CREDENTIALS_INVALID == "credentials_invalid"
