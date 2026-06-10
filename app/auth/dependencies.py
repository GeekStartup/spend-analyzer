from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer

from app.auth.jwt_validator import JwtValidationError, validate_access_token
from app.observability.logging import get_logger
from app.observability.metrics import record_auth_failure
from app.problem_details import PROBLEM_TYPE_PREFIX, ProblemException
from app.schemas.auth_schema import AuthenticatedUser

AUTH_FAILURE_MISSING_CREDENTIALS = "missing_credentials"
AUTH_FAILURE_CREDENTIALS_INVALID = "credentials_invalid"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
logger = get_logger(__name__)


def unauthorized_exception(*, missing: bool = False) -> ProblemException:
    problem_type = "authentication-required" if missing else "invalid-credentials"
    title = "Authentication required" if missing else "Authentication failed"

    return ProblemException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        type=f"{PROBLEM_TYPE_PREFIX}{problem_type}",
        title=title,
        detail="Valid bearer credentials are required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(token: str | None = Depends(oauth2_scheme)) -> AuthenticatedUser:
    if not token:
        record_auth_failure(AUTH_FAILURE_MISSING_CREDENTIALS)
        logger.info("Authentication failed because credentials were missing")
        raise unauthorized_exception(missing=True)

    try:
        claims = validate_access_token(token)
    except JwtValidationError as error:
        record_auth_failure(AUTH_FAILURE_CREDENTIALS_INVALID)
        logger.info(
            "Authentication failed because credentials were invalid",
            exception_type=error.__class__.__name__,
        )
        raise unauthorized_exception() from error

    return AuthenticatedUser(
        user_id=claims["sub"],
        username=claims.get("preferred_username"),
        email=claims.get("email"),
    )
