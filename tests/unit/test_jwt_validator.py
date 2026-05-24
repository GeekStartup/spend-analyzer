from unittest.mock import Mock

import pytest
from jose import ExpiredSignatureError, JWTError

from app.auth.jwt_validator import (
    JwtValidationError,
    get_jwks,
    get_signing_key,
    validate_access_token,
)


@pytest.fixture(autouse=True)
def clear_jwks_cache():
    get_jwks.cache_clear()
    yield
    get_jwks.cache_clear()


def test_get_jwks_fetches_configured_url_and_caches_response(monkeypatch):
    response = Mock()
    response.json.return_value = {"keys": [{"kid": "key-1"}]}
    response.raise_for_status.return_value = None
    get_mock = Mock(return_value=response)

    monkeypatch.setattr("app.auth.jwt_validator.requests.get", get_mock)
    monkeypatch.setattr("app.auth.jwt_validator.settings.oidc_jwks_url", "jwks-url")

    assert get_jwks() == {"keys": [{"kid": "key-1"}]}
    assert get_jwks() == {"keys": [{"kid": "key-1"}]}

    get_mock.assert_called_once_with("jwks-url", timeout=5)
    response.raise_for_status.assert_called_once()


def test_get_signing_key_returns_matching_key(monkeypatch):
    monkeypatch.setattr(
        "app.auth.jwt_validator.jwt.get_unverified_header",
        lambda value: {"kid": "key-2"},
    )
    monkeypatch.setattr(
        "app.auth.jwt_validator.get_jwks",
        lambda: {"keys": [{"kid": "key-1"}, {"kid": "key-2", "kty": "RSA"}]},
    )

    signing_key = get_signing_key("value")

    assert signing_key == {"kid": "key-2", "kty": "RSA"}


def test_get_signing_key_raises_for_malformed_header(monkeypatch):
    def fake_get_unverified_header(value: str):
        raise JWTError("bad header")

    monkeypatch.setattr(
        "app.auth.jwt_validator.jwt.get_unverified_header",
        fake_get_unverified_header,
    )

    with pytest.raises(JwtValidationError, match="Malformed token header"):
        get_signing_key("value")


def test_get_signing_key_raises_when_header_has_no_key_id(monkeypatch):
    monkeypatch.setattr(
        "app.auth.jwt_validator.jwt.get_unverified_header",
        lambda value: {},
    )

    with pytest.raises(JwtValidationError, match="does not contain kid"):
        get_signing_key("value")


def test_get_signing_key_raises_when_matching_key_is_missing(monkeypatch):
    monkeypatch.setattr(
        "app.auth.jwt_validator.jwt.get_unverified_header",
        lambda value: {"kid": "missing-key"},
    )
    monkeypatch.setattr(
        "app.auth.jwt_validator.get_jwks",
        lambda: {"keys": [{"kid": "other-key"}]},
    )

    with pytest.raises(JwtValidationError, match="Matching signing key was not found"):
        get_signing_key("value")


def test_validate_access_token_returns_claims_for_valid_value(monkeypatch):
    expected_claims = {"sub": "user-123", "preferred_username": "test.user"}

    monkeypatch.setattr(
        "app.auth.jwt_validator.get_signing_key",
        lambda value: {"kid": "key-1"},
    )
    decode_mock = Mock(return_value=expected_claims)
    monkeypatch.setattr("app.auth.jwt_validator.jwt.decode", decode_mock)
    monkeypatch.setattr("app.auth.jwt_validator.settings.oidc_audience", "audience")
    monkeypatch.setattr("app.auth.jwt_validator.settings.oidc_issuer_url", "issuer")

    claims = validate_access_token("value")

    assert claims == expected_claims
    decode_mock.assert_called_once_with(
        token="value",
        key={"kid": "key-1"},
        algorithms=["RS256"],
        audience="audience",
        issuer="issuer",
    )


def test_validate_access_token_raises_when_value_is_expired(monkeypatch):
    monkeypatch.setattr(
        "app.auth.jwt_validator.get_signing_key",
        lambda value: {"kid": "key-1"},
    )

    def fake_decode(**kwargs):
        raise ExpiredSignatureError("expired")

    monkeypatch.setattr("app.auth.jwt_validator.jwt.decode", fake_decode)

    with pytest.raises(JwtValidationError, match="Token has expired"):
        validate_access_token("value")


def test_validate_access_token_raises_when_decode_fails(monkeypatch):
    monkeypatch.setattr(
        "app.auth.jwt_validator.get_signing_key",
        lambda value: {"kid": "key-1"},
    )

    def fake_decode(**kwargs):
        raise JWTError("invalid")

    monkeypatch.setattr("app.auth.jwt_validator.jwt.decode", fake_decode)

    with pytest.raises(JwtValidationError, match="Token validation failed"):
        validate_access_token("value")


def test_validate_access_token_raises_when_subject_is_missing(monkeypatch):
    monkeypatch.setattr(
        "app.auth.jwt_validator.get_signing_key",
        lambda value: {"kid": "key-1"},
    )
    monkeypatch.setattr(
        "app.auth.jwt_validator.jwt.decode",
        lambda **kwargs: {"preferred_username": "test.user"},
    )

    with pytest.raises(JwtValidationError, match="does not contain subject"):
        validate_access_token("value")
