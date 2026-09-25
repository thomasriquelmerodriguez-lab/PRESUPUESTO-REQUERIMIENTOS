from datetime import datetime

from pydantic import Field

from app.schemas.common import ApiModel


class AccountView(ApiModel):
    id: str
    code: str
    name: str
    matrix_code: str
    parent_code: str | None
    level: int
    budget: int
    base_new_requirements: int
    pending_requirements: int
    new_requirements: int
    obligated_cas: int
    available: int
    row_version: int


class BudgetCatalog(ApiModel):
    area: str
    year: int
    version_id: str
    source_name: str
    total_budget: int
    total_new_requirements: int
    total_obligated_cas: int
    total_available: int
    accounts: list[AccountView]


class DashboardMetrics(ApiModel):
    area: str
    year: int
    requirements_count: int
    requirements_amount: int
    accounts_used: int
    total_budget: int
    total_new_requirements: int
    total_obligated_cas: int
    total_available: int


class ObligatedCasUpdate(ApiModel):
    amount: int = Field(ge=0, le=9_000_000_000_000_000)
    row_version: int = Field(ge=1)


class ImportPreviewRow(ApiModel):
    code: str
    name: str
    budget: int
    base_new_requirements: int
    obligated_cas: int
    included: bool
    reason: str


class ImportPreview(ApiModel):
    token: str
    area: str
    year: int
    filename: str
    rows_read: int
    valid_rows: int
    included_rows: int
    excluded_rows: int
    total_budget: int
    total_new_requirements: int
    total_obligated_cas: int
    sample: list[ImportPreviewRow]


class ImportApply(ApiModel):
    token: str = Field(min_length=20, max_length=200)
    area: str = Field(pattern=r"^(municipal|salud|educacion)$")
    year: int = Field(ge=2020, le=2100)


class BudgetVersionView(ApiModel):
    id: str
    area: str
    year: int
    version_number: int
    active: bool
    is_seed: bool
    source_name: str
    total_budget: int
    created_at: datetime


class BudgetPeriodCreate(ApiModel):
    year: int = Field(ge=2020, le=2100)


class BudgetPeriodView(ApiModel):
    id: str
    area: str
    year: int
    active: bool
    has_budget: bool
    active_version: int | None = None
    source_name: str | None = None
    total_budget: int = 0
    created_at: datetime
