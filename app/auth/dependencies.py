from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.auth.jwt_validator import JwtValidationError, validate_access_token
from app.observability.metrics import record_auth_failure
from app.schemas.auth_schema import AuthenticatedUser

AUTH_FAILURE_MISSING_CREDENTIALS = "missing_credentials"
AUTH_FAILURE_CREDENTIALS_INVALID = "credentials_invalid"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


def unauthorized_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(token: str | None = Depends(oauth2_scheme)) -> AuthenticatedUser:
    if not token:
        record_auth_failure(AUTH_FAILURE_MISSING_CREDENTIALS)
        raise unauthorized_exception()

    try:
        claims = validate_access_token(token)
    except JwtValidationError as error:
        record_auth_failure(AUTH_FAILURE_CREDENTIALS_INVALID)
        raise unauthorized_exception() from error

    return AuthenticatedUser(
        user_id=claims["sub"],
        username=claims.get("preferred_username"),
        email=claims.get("email"),
    )
