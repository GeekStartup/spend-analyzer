from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.auth.jwt_validator import JwtValidationError, validate_access_token
from app.schemas.auth_schema import AuthenticatedUser


outh2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_current_user(token: str = Depends(outh2_scheme)) -> AuthenticatedUser:
    try:
        claims = validate_access_token(token)
    except JwtValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    return AuthenticatedUser(
        user_id=claims["sub"],
        username=claims.get("preferred_username"),
        email=claims.get("email"),
    )
