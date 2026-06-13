from unittest.mock import Mock

import pytest
import requests
from jose import ExpiredSignatureError, JWTError

from app.auth import jwt_validator
from app.auth.jwt_validator import (
    JwtValidationError,
    get_jwks,
    get_signing_key,
    validate_access_token,
)
from app.errors import IdentityProviderUnavailableError


def usable_jwk(key_id: str = "key-1") -> dict[str, str]:
    return {
        "kid": key_id,
        "kty": "RSA",
        "n": "modulus",
        "e": "AQAB",
        "use": "sig",
        "alg": "RS256",
    }


@pytest.fixture(autouse=True)
def clear_jwks_cache():
    get_jwks.cache_clear()
    yield
    get_jwks.cache_clear()


def test_get_jwks_fetches_once_filters_keys_and_records_success(monkeypatch):
    response = Mock()
    response.json.return_value = {
        "keys": [
            {"kid": "incomplete"},
            usable_jwk(),
        ]
    }
    response.raise_for_status.return_value = None
    request = Mock(return_value=response)
    metric = Mock()

    monkeypatch.setattr(jwt_validator.requests, "get", request)
    monkeypatch.setattr(jwt_validator, "record_dependency_health", metric)
    monkeypatch.setattr(jwt_validator.settings, "oidc_jwks_url", "jwks-url")

    expected = {"keys": [usable_jwk()]}
    assert get_jwks() == expected
    assert get_jwks() == expected
    request.assert_called_once_with("jwks-url", timeout=5)
    metric.assert_called_once_with("identity_provider", True)


def test_get_jwks_timeout_raises_typed_error_with_timeout_context(monkeypatch):
    metric = Mock()
    monkeypatch.setattr(
        jwt_validator.requests,
        "get",
        Mock(side_effect=requests.Timeout("request timed out")),
    )
    monkeypatch.setattr(jwt_validator, "record_dependency_health", metric)

    with pytest.raises(IdentityProviderUnavailableError) as error:
        get_jwks()

    assert error.value.context == {
        "dependency": "identity_provider",
        "operation": "jwks_fetch",
        "failure_category": "request_failed",
        "cause_type": "Timeout",
        "timeout_seconds": 5,
    }
    metric.assert_called_once_with("identity_provider", False)


def test_get_jwks_non_timeout_failure_omits_timeout_context(monkeypatch):
    metric = Mock()
    monkeypatch.setattr(
        jwt_validator.requests,
        "get",
        Mock(side_effect=requests.ConnectionError("connection failed")),
    )
    monkeypatch.setattr(jwt_validator, "record_dependency_health", metric)

    with pytest.raises(IdentityProviderUnavailableError) as error:
        get_jwks()

    assert error.value.context == {
        "dependency": "identity_provider",
        "operation": "jwks_fetch",
        "failure_category": "request_failed",
        "cause_type": "ConnectionError",
    }
    metric.assert_called_once_with("identity_provider", False)


@pytest.mark.parametrize(
    "payload",
    [
        {"unexpected": []},
        {"keys": []},
        {"keys": [{"kid": "incomplete"}]},
        {"keys": [{"kid": "key-1", "kty": "EC", "n": "n", "e": "e"}]},
        ["unexpected"],
    ],
)
def test_get_jwks_rejects_unusable_response(payload, monkeypatch):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    metric = Mock()
    monkeypatch.setattr(jwt_validator.requests, "get", Mock(return_value=response))
    monkeypatch.setattr(jwt_validator, "record_dependency_health", metric)

    with pytest.raises(IdentityProviderUnavailableError) as error:
        get_jwks()

    assert error.value.context["failure_category"] == "invalid_response"
    metric.assert_called_once_with("identity_provider", False)


def test_get_signing_key_returns_matching_key(monkeypatch):
    monkeypatch.setattr(
        jwt_validator.jwt,
        "get_unverified_header",
        lambda _value: {"kid": "key-2"},
    )
    monkeypatch.setattr(
        jwt_validator,
        "get_jwks",
        lambda: {"keys": [usable_jwk("key-1"), usable_jwk("key-2")]},
    )

    assert get_signing_key("value") == usable_jwk("key-2")


def test_get_signing_key_rejects_malformed_header(monkeypatch):
    def fail_header(_value: str):
        raise JWTError("bad header")

    monkeypatch.setattr(jwt_validator.jwt, "get_unverified_header", fail_header)

    with pytest.raises(JwtValidationError, match="Malformed token header"):
        get_signing_key("value")


def test_get_signing_key_requires_key_id(monkeypatch):
    monkeypatch.setattr(jwt_validator.jwt, "get_unverified_header", lambda _value: {})

    with pytest.raises(JwtValidationError, match="does not contain kid"):
        get_signing_key("value")


def test_get_signing_key_requires_matching_key(monkeypatch):
    monkeypatch.setattr(
        jwt_validator.jwt,
        "get_unverified_header",
        lambda _value: {"kid": "missing"},
    )
    monkeypatch.setattr(
        jwt_validator,
        "get_jwks",
        lambda: {"keys": [usable_jwk("other")]},
    )

    with pytest.raises(JwtValidationError, match="Matching signing key was not found"):
        get_signing_key("value")


def test_validate_access_token_returns_claims(monkeypatch):
    claims = {"sub": "user-123"}
    monkeypatch.setattr(
        jwt_validator,
        "get_signing_key",
        lambda _value: usable_jwk(),
    )
    decode = Mock(return_value=claims)
    monkeypatch.setattr(jwt_validator.jwt, "decode", decode)

    assert validate_access_token("value") == claims
    decode.assert_called_once_with(
        token="value",
        key=usable_jwk(),
        algorithms=["RS256"],
        audience=jwt_validator.settings.oidc_audience,
        issuer=jwt_validator.settings.oidc_issuer_url,
    )


def test_validate_access_token_maps_expired_signature(monkeypatch):
    monkeypatch.setattr(
        jwt_validator,
        "get_signing_key",
        lambda _value: usable_jwk(),
    )

    def reject_decode(**_kwargs):
        raise ExpiredSignatureError("expired")

    monkeypatch.setattr(jwt_validator.jwt, "decode", reject_decode)

    with pytest.raises(JwtValidationError, match="Token has expired"):
        validate_access_token("value")


def test_validate_access_token_maps_decode_failure(monkeypatch):
    monkeypatch.setattr(
        jwt_validator,
        "get_signing_key",
        lambda _value: usable_jwk(),
    )

    def reject_decode(**_kwargs):
        raise JWTError("invalid")

    monkeypatch.setattr(jwt_validator.jwt, "decode", reject_decode)

    with pytest.raises(JwtValidationError, match="Token validation failed"):
        validate_access_token("value")


def test_validate_access_token_requires_subject(monkeypatch):
    monkeypatch.setattr(
        jwt_validator,
        "get_signing_key",
        lambda _value: usable_jwk(),
    )
    monkeypatch.setattr(jwt_validator.jwt, "decode", lambda **_kwargs: {})

    with pytest.raises(JwtValidationError, match="does not contain subject"):
        validate_access_token("value")
