import pytest
from fastapi import HTTPException

from app.auth.dependencies import get_current_user


def test_get_current_user_returns_authenticated_user(monkeypatch):
    def fake_validate_access_token(token: str):
        assert token == "valid-token"

        return {
            "sub": "user-123",
            "preferred_username": "test.user",
            "email": "test.user@example.com",
        }

    monkeypatch.setattr(
        "app.auth.dependencies.validate_access_token",
        fake_validate_access_token,
    )

    current_user = get_current_user(token="valid-token")

    assert current_user.user_id == "user-123"
    assert current_user.username == "test.user"
    assert current_user.email == "test.user@example.com"


def test_get_current_user_raises_401_for_invalid_token(monkeypatch):
    from app.auth.jwt_validator import JwtValidationError

    def fake_validate_access_token(token: str):
        raise JwtValidationError("invalid token")

    monkeypatch.setattr(
        "app.auth.dependencies.validate_access_token",
        fake_validate_access_token,
    )

    with pytest.raises(HTTPException) as error:
        get_current_user(token="invalid-token")

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid authentication credentials"
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}
