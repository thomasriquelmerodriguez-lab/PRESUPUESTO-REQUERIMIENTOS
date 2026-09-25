from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.core.permissions import PERMISSION_CODES
from app.schemas.common import ApiModel


class PermissionView(ApiModel):
    code: str
    label: str
    description: str
    category: str


class UserAdminView(ApiModel):
    id: str
    display_name: str
    active: bool
    role: str
    areas: list[str]
    permissions: list[str]
    created_at: datetime
    updated_at: datetime
    is_current_user: bool = False


class UserCreate(ApiModel):
    display_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=4, max_length=128)
    areas: list[str] = Field(default_factory=list, max_length=3)
    permissions: list[str] = Field(default_factory=list, max_length=30)
    active: bool = True

    @field_validator("areas")
    @classmethod
    def normalize_areas(cls, value: list[str]) -> list[str]:
        return sorted(set(item.strip().lower() for item in value if item.strip()))

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: list[str]) -> list[str]:
        normalized = sorted(set(item.strip() for item in value if item.strip()))
        invalid = [item for item in normalized if item not in PERMISSION_CODES]
        if invalid:
            raise ValueError("Uno o más privilegios no son válidos.")
        return normalized

    @model_validator(mode="after")
    def validate_area_permissions(self):
        if self.active and not self.permissions:
            raise ValueError("Asigne al menos un privilegio al usuario activo.")
        area_permissions = [p for p in self.permissions if not p.startswith("audit.") and p != "users.manage"]
        if area_permissions and not self.areas:
            raise ValueError("Seleccione al menos un área para los privilegios operativos.")
        return self


class UserUpdate(ApiModel):
    display_name: str = Field(min_length=2, max_length=120)
    areas: list[str] = Field(default_factory=list, max_length=3)
    permissions: list[str] = Field(default_factory=list, max_length=30)
    active: bool = True

    @field_validator("areas")
    @classmethod
    def normalize_areas(cls, value: list[str]) -> list[str]:
        return sorted(set(item.strip().lower() for item in value if item.strip()))

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: list[str]) -> list[str]:
        normalized = sorted(set(item.strip() for item in value if item.strip()))
        invalid = [item for item in normalized if item not in PERMISSION_CODES]
        if invalid:
            raise ValueError("Uno o más privilegios no son válidos.")
        return normalized

    @model_validator(mode="after")
    def validate_area_permissions(self):
        if self.active and not self.permissions:
            raise ValueError("Asigne al menos un privilegio al usuario activo.")
        area_permissions = [p for p in self.permissions if not p.startswith("audit.") and p != "users.manage"]
        if area_permissions and not self.areas:
            raise ValueError("Seleccione al menos un área para los privilegios operativos.")
        return self


class PasswordReset(ApiModel):
    password: str = Field(min_length=4, max_length=128)
