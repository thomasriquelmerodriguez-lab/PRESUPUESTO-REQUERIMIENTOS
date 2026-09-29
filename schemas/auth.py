from pydantic import Field, model_validator

from app.schemas.common import ApiModel


class LoginRequest(ApiModel):
    user_id: str | None = Field(default=None, min_length=1, max_length=36)
    username: str | None = Field(default=None, min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def require_identity(self):
        if not self.user_id and not self.username:
            raise ValueError("Seleccione un usuario.")
        return self


class LoginOption(ApiModel):
    id: str
    display_name: str


class UserSession(ApiModel):
    id: str
    username: str
    display_name: str
    role: str
    areas: list[str]
    permissions: list[str]


class SessionResponse(ApiModel):
    user: UserSession
    csrf_token: str
