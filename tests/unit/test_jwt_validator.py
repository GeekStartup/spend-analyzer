from contextlib import nullcontext
from unittest.mock import Mock

import pytest
import requests
from jose import ExpiredSignatureError, JWTError
from opentelemetry.trace import StatusCode

from app.auth import jwt_validator
from app.auth.jwt_validator import (
    IdentityProviderUnavailableError,
    JwtValidationError,
    get_jwks,
    get_signing_key,
    validate_access_token,
)


class EventRecordingSpan:
    def __init__(self):
        self.attributes = {}
        self.events = []
        self.status = None

    def add_event(self, name, attributes=None):
        self.events.append((name, attributes))

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def set_status(self, status):
        self.status = status


@pytest.fixture(autouse=True)
def clear_jwks_cache():
    get_jwks.cache_clear()
    yield
    get_jwks.cache_clear()


def patch_jwks_observability(monkeypatch):
    span = EventRecordingSpan()
    start_span = Mock(return_value=nullcontext(span))
    dependency_metric = Mock()
    logger = Mock()
    suppress_instrumentation = Mock(return_value=nullcontext())

    monkeypatch.setattr(jwt_validator, "start_span", start_span)
    monkeypatch.setattr(
        jwt_validator,
        "record_dependency_health",
        dependency_metric,
    )
    monkeypatch.setattr(jwt_validator, "logger", logger)
    monkeypatch.setattr(
        jwt_validator,
        "suppress_http_instrumentation",
        suppress_instrumentation,
    )

    return {
        "span": span,
        "start_span": start_span,
        "dependency_metric": dependency_metric,
        "logger": logger,
        "suppress_instrumentation": suppress_instrumentation,
    }


def test_get_jwks_fetches_caches_and_records_dependency_success(monkeypatch):
    observability = patch_jwks_observability(monkeypatch)
    response = Mock()
    response.json.return_value = {"keys": [{"kid": "key-1"}]}
    response.raise_for_status.return_value = None
    get_mock = Mock(return_value=response)

    monkeypatch.setattr(jwt_validator.requests, "get", get_mock)
    monkeypatch.setattr(jwt_validator.settings, "oidc_jwks_url", "jwks-url")

    assert get_jwks() == {"keys": [{"kid": "key-1"}]}
    assert get_jwks() == {"keys": [{"kid": "key-1"}]}

    get_mock.assert_called_once_with(
        "jwks-url",
        timeout=jwt_validator.JWKS_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status.assert_called_once_with()
    observability["suppress_instrumentation"].assert_called_once_with()
    observability["start_span"].assert_called_once_with(
        "identity_provider.jwks_fetch",
        attributes={
            "app.dependency.name": "identity_provider",
            "app.operation": "jwks_fetch",
        },
    )
    observability["dependency_metric"].assert_called_once_with(
        "identity_provider",
        True,
    )
    assert observability["span"].attributes == {"app.outcome": "succeeded"}
    assert observability["span"].events == []
    assert observability["span"].status is None
    observability["logger"].debug.assert_called_once_with(
        "JWKS cache miss; retrieving signing keys"
    )
    observability["logger"].warning.assert_not_called()


def test_get_jwks_records_safe_timeout_failure(monkeypatch):
    observability = patch_jwks_observability(monkeypatch)
    sensitive_message = "timeout calling https://identity.internal/certs?token=secret"
    timeout_error = requests.Timeout(sensitive_message)
    monkeypatch.setattr(
        jwt_validator.requests,
        "get",
        Mock(side_effect=timeout_error),
    )

    with pytest.raises(IdentityProviderUnavailableError):
        get_jwks()

    observability["dependency_metric"].assert_called_once_with(
        "identity_provider",
        False,
    )
    assert observability["span"].attributes == {
        "app.outcome": "failed",
        "app.failure.category": "request_failed",
    }
    assert observability["span"].status.status_code == StatusCode.ERROR
    assert observability["span"].events == [
        ("exception", {"exception.type": "Timeout"})
    ]
    observability["logger"].warning.assert_called_once_with(
        "Identity provider key retrieval failed",
        dependency="identity_provider",
        operation="jwks_fetch",
        exception_type="Timeout",
        timeout_seconds=5,
    )
    assert sensitive_message not in str(observability["logger"].warning.call_args)


def test_get_jwks_records_invalid_response_without_payload(monkeypatch):
    observability = patch_jwks_observability(monkeypatch)
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"payload": "sensitive-provider-value"}
    monkeypatch.setattr(jwt_validator.requests, "get", Mock(return_value=response))

    with pytest.raises(IdentityProviderUnavailableError):
        get_jwks()

    observability["dependency_metric"].assert_called_once_with(
        "identity_provider",
        False,
    )
    assert observability["span"].attributes["app.failure.category"] == (
        "invalid_response"
    )
    observability["logger"].warning.assert_called_once_with(
        "Identity provider returned an invalid signing-key response",
        dependency="identity_provider",
        operation="jwks_fetch",
        exception_type="ValueError",
    )
    assert "sensitive-provider-value" not in str(
        observability["logger"].warning.call_args
    )


def test_get_signing_key_returns_matching_key(monkeypatch):
    monkeypatch.setattr(
        jwt_validator.jwt,
        "get_unverified_header",
        lambda value: {"kid": "key-2"},
    )
    monkeypatch.setattr(
        jwt_validator,
        "get_jwks",
        lambda: {"keys": [{"kid": "key-1"}, {"kid": "key-2", "kty": "RSA"}]},
    )

    signing_key = get_signing_key("value")

    assert signing_key == {"kid": "key-2", "kty": "RSA"}


def test_get_signing_key_raises_for_malformed_header(monkeypatch):
    def fake_get_unverified_header(value: str):
        raise JWTError("bad header")

    monkeypatch.setattr(
        jwt_validator.jwt,
        "get_unverified_header",
        fake_get_unverified_header,
    )

    with pytest.raises(JwtValidationError, match="Malformed token header"):
        get_signing_key("value")


def test_get_signing_key_raises_when_header_has_no_key_id(monkeypatch):
    monkeypatch.setattr(
        jwt_validator.jwt,
        "get_unverified_header",
        lambda value: {},
    )

    with pytest.raises(JwtValidationError, match="does not contain kid"):
        get_signing_key("value")


def test_get_signing_key_raises_when_matching_key_is_missing(monkeypatch):
    monkeypatch.setattr(
        jwt_validator.jwt,
        "get_unverified_header",
        lambda value: {"kid": "missing-key"},
    )
    monkeypatch.setattr(
        jwt_validator,
        "get_jwks",
        lambda: {"keys": [{"kid": "other-key"}]},
    )

    with pytest.raises(JwtValidationError, match="Matching signing key was not found"):
        get_signing_key("value")


def test_validate_access_token_returns_claims_for_valid_value(monkeypatch):
    expected_claims = {"sub": "user-123", "preferred_username": "test.user"}
    monkeypatch.setattr(
        jwt_validator,
        "get_signing_key",
        lambda value: {"kid": "key-1"},
    )
    decode_mock = Mock(return_value=expected_claims)
    monkeypatch.setattr(jwt_validator.jwt, "decode", decode_mock)
    monkeypatch.setattr(jwt_validator.settings, "oidc_audience", "audience")
    monkeypatch.setattr(jwt_validator.settings, "oidc_issuer_url", "issuer")

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
        jwt_validator,
        "get_signing_key",
        lambda value: {"kid": "key-1"},
    )

    def fake_decode(**kwargs):
        raise ExpiredSignatureError("expired")

    monkeypatch.setattr(jwt_validator.jwt, "decode", fake_decode)

    with pytest.raises(JwtValidationError, match="Token has expired"):
        validate_access_token("value")


def test_validate_access_token_raises_when_decode_fails(monkeypatch):
    monkeypatch.setattr(
        jwt_validator,
        "get_signing_key",
        lambda value: {"kid": "key-1"},
    )

    def fake_decode(**kwargs):
        raise JWTError("invalid")

    monkeypatch.setattr(jwt_validator.jwt, "decode", fake_decode)

    with pytest.raises(JwtValidationError, match="Token validation failed"):
        validate_access_token("value")


def test_validate_access_token_raises_when_subject_is_missing(monkeypatch):
    monkeypatch.setattr(
        jwt_validator,
        "get_signing_key",
        lambda value: {"kid": "key-1"},
    )
    monkeypatch.setattr(
        jwt_validator.jwt,
        "decode",
        lambda **kwargs: {"preferred_username": "test.user"},
    )

    with pytest.raises(JwtValidationError, match="does not contain subject"):
        validate_access_token("value")
