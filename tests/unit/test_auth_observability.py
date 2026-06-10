from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.auth import dependencies
from app.auth.jwt_validator import (
    IdentityProviderUnavailableError,
    JwtValidationError,
)


def test_missing_credentials_records_metric_and_useful_log(monkeypatch):
    recorded_categories = []
    logger = Mock()
    monkeypatch.setattr(
        dependencies,
        "record_auth_failure",
        recorded_categories.append,
    )
    monkeypatch.setattr(dependencies, "logger", logger)
    monkeypatch.setattr(
        dependencies,
        "validate_access_token",
        lambda _token: raise_assertion("Token validator must not be called"),
    )

    with pytest.raises(HTTPException) as error:
        dependencies.get_current_user(token=None)

    assert error.value.status_code == 401
    assert recorded_categories == [dependencies.AUTH_FAILURE_MISSING_CREDENTIALS]
    logger.info.assert_called_once_with(
        "Authentication failed because credentials were missing"
    )


def test_invalid_token_records_metric_and_safe_log(monkeypatch):
    recorded_categories = []
    logger = Mock()

    def reject_token(_token: str):
        raise JwtValidationError("sensitive token validation message")

    monkeypatch.setattr(dependencies, "validate_access_token", reject_token)
    monkeypatch.setattr(
        dependencies,
        "record_auth_failure",
        recorded_categories.append,
    )
    monkeypatch.setattr(dependencies, "logger", logger)

    with pytest.raises(HTTPException) as error:
        dependencies.get_current_user(token="invalid-token")

    assert error.value.status_code == 401
    assert recorded_categories == [dependencies.AUTH_FAILURE_CREDENTIALS_INVALID]
    logger.info.assert_called_once_with(
        "Authentication failed because credentials were invalid",
        exception_type="JwtValidationError",
    )
    assert "sensitive token validation message" not in str(logger.info.call_args)
    assert "invalid-token" not in str(logger.info.call_args)


def test_identity_provider_failure_returns_503_without_auth_failure_metric(monkeypatch):
    auth_failure_metric = Mock()
    logger = Mock()

    def fail_validation(_token: str):
        raise IdentityProviderUnavailableError("sensitive provider detail")

    monkeypatch.setattr(dependencies, "validate_access_token", fail_validation)
    monkeypatch.setattr(dependencies, "record_auth_failure", auth_failure_metric)
    monkeypatch.setattr(dependencies, "logger", logger)

    with pytest.raises(HTTPException) as error:
        dependencies.get_current_user(token="valid-looking-token")

    assert error.value.status_code == 503
    assert error.value.detail == (
        "Authentication could not be completed. Try again later."
    )
    auth_failure_metric.assert_not_called()
    logger.info.assert_not_called()


def raise_assertion(message: str):
    raise AssertionError(message)
