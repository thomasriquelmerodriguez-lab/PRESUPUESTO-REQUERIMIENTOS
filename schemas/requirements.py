from datetime import date, datetime

from pydantic import Field, field_validator

from app.schemas.common import ApiModel


class RequirementCreate(ApiModel):
    area: str = Field(pattern=r"^(municipal|salud|educacion)$")
    budget_year: int = Field(ge=2020, le=2100)
    request_date: date
    expedient: str = Field(min_length=1, max_length=120)
    subject: str = Field(min_length=1, max_length=1000)
    amount: int = Field(gt=0, le=9_000_000_000_000_000)
    department: str = Field(default="", max_length=250)
    management_area: str = Field(default="", max_length=250)
    notes: str = Field(default="", max_length=5000)
    account_code: str = Field(min_length=5, max_length=40, pattern=r"^[0-9-]+$")
    allow_over_budget: bool = False
    over_budget_reason: str = Field(default="", max_length=500)

    @field_validator("over_budget_reason")
    @classmethod
    def validate_reason(cls, value: str, info):
        if info.data.get("allow_over_budget") and len(value.strip()) < 5:
            raise ValueError("Debe indicar un motivo para exceder el presupuesto disponible.")
        return value


class RequirementUpdate(RequirementCreate):
    version: int = Field(ge=1)


class RequirementView(ApiModel):
    id: str
    area: str
    budget_year: int
    request_date: date
    expedient: str
    subject: str
    amount: int
    department: str
    management_area: str
    notes: str
    account_code: str
    account_name: str = ""
    matrix_code: str = ""
    included_in_base: bool
    version: int
    locked_by: str | None = None
    lock_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RequirementList(ApiModel):
    items: list[RequirementView]
    total: int
    total_amount: int
    page: int
    page_size: int


class LockResponse(ApiModel):
    acquired: bool
    lock_expires_at: datetime
    locked_by: str
