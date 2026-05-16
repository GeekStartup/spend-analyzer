from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    user_id: str
    username: str | None = None
    email: str | None = None


class MeResponse(BaseModel):
    user_id: str
    username: str | None = None
    email: str | None = None
