from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.schemas.auth_schema import AuthenticatedUser, MeResponse


router = APIRouter(tags=["Users"])


@router.get("/me", response_model=MeResponse)
def get_me(current_user: AuthenticatedUser = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        email=current_user.email,
    )
