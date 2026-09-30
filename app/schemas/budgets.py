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


class DashboardAccountBreakdown(ApiModel):
    code: str
    name: str
    level: int
    budget: int
    requirements: int
    obligated_cas: int
    available: int
    committed_percent: float
    status: str


class DashboardMonth(ApiModel):
    month: int
    label: str
    requirements_count: int
    requirements_amount: int


class DashboardAttention(ApiModel):
    negative_balance_accounts: int
    over_90_percent_accounts: int
    low_balance_accounts: int
    unmapped_requirements_count: int
    unmapped_requirements_amount: int


class DecisionDashboard(ApiModel):
    area: str
    year: int
    scope_code: str | None = None
    scope_name: str | None = None
    requirements_count: int
    accounts_used: int
    total_budget: int
    total_requirements: int
    total_obligated_cas: int
    total_available: int
    committed_percent: float
    breakdown: list[DashboardAccountBreakdown]
    monthly: list[DashboardMonth]
    critical_accounts: list[DashboardAccountBreakdown]
    top_requirement_accounts: list[DashboardAccountBreakdown]
    attention: DashboardAttention


class ObligatedCasUpdate(ApiModel):
    amount: int = Field(ge=0, le=9_000_000_000_000_000)
    row_version: int = Field(ge=1)


class ImportPreviewRow(ApiModel):
    code: str
    name: str
    budget: int
    budget_original: int = 0
    hierarchy_order: int | None = None
    first_order: bool = False
    calculated_from_children: bool = False
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
    previous_total_budget: int = 0
    first_order_accounts: int = 0
    total_new_requirements: int
    total_obligated_cas: int
    new_accounts: int = 0
    modified_accounts: int = 0
    unchanged_uploaded_accounts: int = 0
    retained_accounts: int = 0
    removed_accounts: int = 0
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
