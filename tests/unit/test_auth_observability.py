import pytest
from fastapi import HTTPException

from app.auth import dependencies
from app.auth.jwt_validator import JwtValidationError


def test_missing_credentials_records_bounded_auth_failure(monkeypatch):
    recorded_categories = []

    monkeypatch.setattr(
        dependencies,
        "record_auth_failure",
        recorded_categories.append,
    )
    monkeypatch.setattr(
        dependencies,
        "validate_access_token",
        lambda _token: raise_assertion("Token validator must not be called"),
    )

    with pytest.raises(HTTPException) as error:
        dependencies.get_current_user(token=None)

    assert error.value.status_code == 401
    assert recorded_categories == [dependencies.AUTH_FAILURE_MISSING_CREDENTIALS]


def test_invalid_token_records_bounded_auth_failure(monkeypatch):
    recorded_categories = []

    def reject_token(_token: str):
        raise JwtValidationError("sensitive token validation message")

    monkeypatch.setattr(dependencies, "validate_access_token", reject_token)
    monkeypatch.setattr(
        dependencies,
        "record_auth_failure",
        recorded_categories.append,
    )

    with pytest.raises(HTTPException) as error:
        dependencies.get_current_user(token="invalid-token")

    assert error.value.status_code == 401
    assert recorded_categories == [dependencies.AUTH_FAILURE_CREDENTIALS_INVALID]


def raise_assertion(message: str):
    raise AssertionError(message)
