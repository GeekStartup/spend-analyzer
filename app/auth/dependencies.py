from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.auth.jwt_validator import JwtValidationError, validate_access_token
from app.errors import AuthenticationRequiredError, InvalidCredentialsError
from app.observability.metrics import record_auth_failure
from app.schemas.auth_schema import AuthenticatedUser

AUTH_FAILURE_MISSING_CREDENTIALS = "missing_credentials"
AUTH_FAILURE_CREDENTIALS_INVALID = "credentials_invalid"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


def get_current_user(token: str | None = Depends(oauth2_scheme)) -> AuthenticatedUser:
    if not token:
        record_auth_failure(AUTH_FAILURE_MISSING_CREDENTIALS)
        raise AuthenticationRequiredError(
            "Valid bearer credentials are required.",
            context={"failure_category": AUTH_FAILURE_MISSING_CREDENTIALS},
        )

    try:
        claims = validate_access_token(token)
    except JwtValidationError as error:
        record_auth_failure(AUTH_FAILURE_CREDENTIALS_INVALID)
        raise InvalidCredentialsError(
            "Valid bearer credentials are required.",
            context={
                "failure_category": AUTH_FAILURE_CREDENTIALS_INVALID,
                "cause_type": error.__class__.__name__,
            },
        ) from error

    return AuthenticatedUser(
        user_id=claims["sub"],
        username=claims.get("preferred_username"),
        email=claims.get("email"),
    )
