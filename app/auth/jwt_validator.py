from functools import lru_cache
from typing import Any

from jose import ExpiredSignatureError, JWTError, jwt
import requests

from app.config import settings


class JwtValidationError(Exception):
    """
    Raised when JWT validation fails.
    """


@lru_cache(maxsize=1)
def get_jwks() -> dict[str, Any]:
    """
    Fetch and cache JSON Web Key Set from the configured OIDC provider.

    This is acceptable for MVP/local development. In production, this should
    eventually become a TTL cache because identity providers can rotate keys.
    """
    response = requests.get(settings.oidc_jwks_url, timeout=5)
    response.raise_for_status()

    return response.json()


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
    """
    Validate access token signature, issuer, audience, and expiry.
    """
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
        raise JwtValidationError("Token does not conation subject")

    return claims
