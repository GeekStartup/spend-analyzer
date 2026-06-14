from functools import lru_cache
from typing import Any

import requests
from jose import ExpiredSignatureError, JWTError, jwt

from app.config import settings
from app.errors import IdentityProviderUnavailableError
from app.observability.logging import get_logger
from app.observability.metrics import record_dependency_health

IDENTITY_PROVIDER_DEPENDENCY = "identity_provider"
JWKS_REQUEST_TIMEOUT_SECONDS = 5

JWKS_FAILURE_REQUEST_FAILED = "request_failed"
JWKS_FAILURE_INVALID_RESPONSE = "invalid_response"

logger = get_logger(__name__)


class JwtValidationError(Exception):
    """Raised when JWT validation fails."""


def _dependency_error_context(
    *,
    failure_category: str,
    error: Exception,
) -> dict[str, object]:
    context: dict[str, object] = {
        "dependency": IDENTITY_PROVIDER_DEPENDENCY,
        "operation": "jwks_fetch",
        "failure_category": failure_category,
        "cause_type": error.__class__.__name__,
    }

    if isinstance(error, requests.Timeout):
        context["timeout_seconds"] = JWKS_REQUEST_TIMEOUT_SECONDS

    return context


def _is_usable_signing_key(value: object) -> bool:
    if not isinstance(value, dict):
        return False

    kid = value.get("kid")
    modulus = value.get("n")
    exponent = value.get("e")
    return (
        isinstance(kid, str)
        and bool(kid)
        and value.get("kty") == "RSA"
        and value.get("use", "sig") == "sig"
        and value.get("alg", "RS256") == "RS256"
        and isinstance(modulus, str)
        and bool(modulus)
        and isinstance(exponent, str)
        and bool(exponent)
    )


def _validate_jwks_response(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Invalid JWKS response structure")

    keys = value.get("keys")
    if not isinstance(keys, list) or not keys:
        raise ValueError("JWKS response contains no signing keys")
    if not all(isinstance(key, dict) for key in keys):
        raise ValueError("Invalid JWKS response structure")
    if not any(_is_usable_signing_key(key) for key in keys):
        raise ValueError("JWKS response contains no usable signing keys")

    return value


@lru_cache(maxsize=1)
def get_jwks() -> dict[str, Any]:
    """Fetch and cache the configured identity-provider signing keys."""
    logger.debug("JWKS cache miss; retrieving signing keys")

    try:
        response = requests.get(
            settings.oidc_jwks_url,
            timeout=JWKS_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        jwks = _validate_jwks_response(response.json())
    except (requests.JSONDecodeError, TypeError, ValueError) as error:
        record_dependency_health(IDENTITY_PROVIDER_DEPENDENCY, False)
        raise IdentityProviderUnavailableError(
            "Authentication could not be completed. Try again later.",
            context=_dependency_error_context(
                failure_category=JWKS_FAILURE_INVALID_RESPONSE,
                error=error,
            ),
        ) from error
    except requests.RequestException as error:
        record_dependency_health(IDENTITY_PROVIDER_DEPENDENCY, False)
        raise IdentityProviderUnavailableError(
            "Authentication could not be completed. Try again later.",
            context=_dependency_error_context(
                failure_category=JWKS_FAILURE_REQUEST_FAILED,
                error=error,
            ),
        ) from error

    record_dependency_health(IDENTITY_PROVIDER_DEPENDENCY, True)
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
        if key.get("kid") == key_id and _is_usable_signing_key(key):
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
