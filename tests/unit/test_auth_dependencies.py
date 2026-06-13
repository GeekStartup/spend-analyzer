from unittest.mock import Mock

import pytest

from app.auth import dependencies
from app.auth.jwt_validator import JwtValidationError
from app.errors import AuthenticationRequiredError, InvalidCredentialsError


def test_oauth2_scheme_uses_configured_token_url():
    assert dependencies.oauth2_scheme.model.flows.password.tokenUrl == "token"


def test_get_current_user_returns_authenticated_user(monkeypatch):
    validator = Mock(
        return_value={
            "sub": "user-123",
            "preferred_username": "test.user",
            "email": "test.user@example.com",
        }
    )
    auth_failure_metric = Mock()
    monkeypatch.setattr(dependencies, "validate_access_token", validator)
    monkeypatch.setattr(dependencies, "record_auth_failure", auth_failure_metric)

    current_user = dependencies.get_current_user(token="valid-value")

    assert current_user.user_id == "user-123"
    assert current_user.username == "test.user"
    assert current_user.email == "test.user@example.com"
    validator.assert_called_once_with("valid-value")
    auth_failure_metric.assert_not_called()


def test_missing_credentials_raise_typed_error_and_record_metric(monkeypatch):
    auth_failure_metric = Mock()
    validator = Mock()
    monkeypatch.setattr(dependencies, "record_auth_failure", auth_failure_metric)
    monkeypatch.setattr(dependencies, "validate_access_token", validator)

    with pytest.raises(AuthenticationRequiredError) as error:
        dependencies.get_current_user(token=None)

    assert error.value.detail == "Valid bearer credentials are required."
    assert error.value.context == {"failure_category": "missing_credentials"}
    auth_failure_metric.assert_called_once_with("missing_credentials")
    validator.assert_not_called()


def test_invalid_credentials_raise_typed_error_with_safe_context(monkeypatch):
    auth_failure_metric = Mock()

    def reject_value(_value: str):
        raise JwtValidationError("sensitive validation detail")

    monkeypatch.setattr(dependencies, "validate_access_token", reject_value)
    monkeypatch.setattr(dependencies, "record_auth_failure", auth_failure_metric)

    with pytest.raises(InvalidCredentialsError) as error:
        dependencies.get_current_user(token="invalid-value")

    assert error.value.detail == "Valid bearer credentials are required."
    assert error.value.context == {
        "failure_category": "credentials_invalid",
        "cause_type": "JwtValidationError",
    }
    assert "sensitive validation detail" not in str(error.value.context)
    auth_failure_metric.assert_called_once_with("credentials_invalid")
