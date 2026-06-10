from functools import lru_cache
from typing import Any

import requests
from jose import ExpiredSignatureError, JWTError, jwt
from opentelemetry.instrumentation.utils import suppress_http_instrumentation
from opentelemetry.trace import Span, Status, StatusCode

from app.config import settings
from app.observability.logging import get_logger
from app.observability.metrics import record_dependency_health
from app.observability.tracing import record_exception_safely, start_span

IDENTITY_PROVIDER_DEPENDENCY = "identity_provider"
JWKS_FETCH_SPAN_NAME = "identity_provider.jwks_fetch"
JWKS_REQUEST_TIMEOUT_SECONDS = 5

JWKS_FAILURE_REQUEST_FAILED = "request_failed"
JWKS_FAILURE_INVALID_RESPONSE = "invalid_response"

logger = get_logger(__name__)


class JwtValidationError(Exception):
    """Raised when JWT validation fails."""


class IdentityProviderUnavailableError(Exception):
    """Raised when signing keys cannot be retrieved safely."""


def _record_jwks_failure(
    *,
    span: Span,
    failure_category: str,
    error: BaseException,
    message: str,
) -> None:
    record_dependency_health(IDENTITY_PROVIDER_DEPENDENCY, False)
    record_exception_safely(span, error)
    span.set_attribute("app.outcome", "failed")
    span.set_attribute("app.failure.category", failure_category)
    span.set_status(
        Status(
            status_code=StatusCode.ERROR,
            description=failure_category,
        )
    )

    log_fields = {
        "dependency": IDENTITY_PROVIDER_DEPENDENCY,
        "operation": "jwks_fetch",
        "exception_type": error.__class__.__name__,
    }
    if isinstance(error, requests.Timeout):
        log_fields["timeout_seconds"] = JWKS_REQUEST_TIMEOUT_SECONDS

    logger.warning(message, **log_fields)


def _validate_jwks_response(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Invalid JWKS response structure")

    keys = value.get("keys")
    if not isinstance(keys, list) or not all(isinstance(key, dict) for key in keys):
        raise ValueError("Invalid JWKS response structure")

    return value


@lru_cache(maxsize=1)
def get_jwks() -> dict[str, Any]:
    """Fetch and cache the configured identity provider signing keys."""
    logger.debug("JWKS cache miss; retrieving signing keys")

    with start_span(
        JWKS_FETCH_SPAN_NAME,
        attributes={
            "app.dependency.name": IDENTITY_PROVIDER_DEPENDENCY,
            "app.operation": "jwks_fetch",
        },
    ) as span:
        try:
            with suppress_http_instrumentation():
                response = requests.get(
                    settings.oidc_jwks_url,
                    timeout=JWKS_REQUEST_TIMEOUT_SECONDS,
                )
            response.raise_for_status()
            jwks = _validate_jwks_response(response.json())
        except (requests.JSONDecodeError, TypeError, ValueError) as error:
            _record_jwks_failure(
                span=span,
                failure_category=JWKS_FAILURE_INVALID_RESPONSE,
                error=error,
                message="Identity provider returned an invalid signing-key response",
            )
            raise IdentityProviderUnavailableError(
                "Identity provider signing-key response is invalid"
            ) from error
        except requests.RequestException as error:
            _record_jwks_failure(
                span=span,
                failure_category=JWKS_FAILURE_REQUEST_FAILED,
                error=error,
                message="Identity provider key retrieval failed",
            )
            raise IdentityProviderUnavailableError(
                "Identity provider signing keys are unavailable"
            ) from error

        record_dependency_health(IDENTITY_PROVIDER_DEPENDENCY, True)
        span.set_attribute("app.outcome", "succeeded")
        return jwks


def get_signing_key(token: str) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as error:
        raise JwtValidationError("Malformed token header") from error

    key_id = header.get("kid")

    if not key_id:
        raise JwtValidationError("Token header does not contain kid")

    jwks = get_jwks()

    for key in jwks.get("keys", []):
        if key.get("kid") == key_id:
            return key

    raise JwtValidationError("Matching signing key was not found")


def validate_access_token(token: str) -> dict[str, Any]:
    """Validate access token signature, issuer, audience, and expiry."""
    signing_key = get_signing_key(token)

    try:
        claims = jwt.decode(
            token=token,
            key=signing_key,
            algorithms=["RS256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer_url,
        )
    except ExpiredSignatureError as error:
        raise JwtValidationError("Token has expired") from error
    except JWTError as error:
        raise JwtValidationError("Token validation failed") from error

    subject = claims.get("sub")

    if not subject:
        raise JwtValidationError("Token does not contain subject")

    return claims
