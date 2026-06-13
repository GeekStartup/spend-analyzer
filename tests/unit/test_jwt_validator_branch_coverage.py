from unittest.mock import Mock

import pytest
from jose import ExpiredSignatureError, JWTError

from app.auth import jwt_validator
from app.auth.jwt_validator import JwtValidationError


def test_get_signing_key_requires_key_id(monkeypatch):
    monkeypatch.setattr(
        jwt_validator.jwt,
        "get_unverified_header",
        lambda _value: {},
    )

    with pytest.raises(JwtValidationError, match="does not contain kid"):
        jwt_validator.get_signing_key("value")


def test_get_signing_key_requires_matching_key(monkeypatch):
    monkeypatch.setattr(
        jwt_validator.jwt,
        "get_unverified_header",
        lambda _value: {"kid": "missing"},
    )
    monkeypatch.setattr(
        jwt_validator,
        "get_jwks",
        lambda: {"keys": [{"kid": "other"}]},
    )

    with pytest.raises(JwtValidationError, match="Matching signing key was not found"):
        jwt_validator.get_signing_key("value")


def test_validate_access_token_maps_expired_signature(monkeypatch):
    monkeypatch.setattr(
        jwt_validator,
        "get_signing_key",
        lambda _value: {"kid": "key-1"},
    )

    def decode(**_kwargs):
        raise ExpiredSignatureError("expired")

    monkeypatch.setattr(jwt_validator.jwt, "decode", decode)

    with pytest.raises(JwtValidationError, match="Token has expired"):
        jwt_validator.validate_access_token("value")


def test_validate_access_token_maps_decode_failure(monkeypatch):
    monkeypatch.setattr(
        jwt_validator,
        "get_signing_key",
        lambda _value: {"kid": "key-1"},
    )
    decode = Mock(side_effect=JWTError("invalid"))
    monkeypatch.setattr(jwt_validator.jwt, "decode", decode)

    with pytest.raises(JwtValidationError, match="Token validation failed"):
        jwt_validator.validate_access_token("value")
