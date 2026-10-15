from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from app.schemas.common import ApiModel

PROCUREMENT_STATUSES = (
    "REGISTRADO",
    "EN_ADQUISICIONES",
    "EN_LICITACION",
    "ADJUDICADO",
    "OC_EMITIDA",
    "CERRADO",
)


class PurchaseOrderCreate(ApiModel):
    order_number: str = Field(min_length=1, max_length=120)
    order_date: date
    supplier: str = Field(min_length=1, max_length=250)
    amount: int = Field(gt=0, le=9_000_000_000_000_000)
    tender_reference: str = Field(default="", max_length=180)
    notes: str = Field(default="", max_length=5000)
    close_requirement: bool = False


class PurchaseOrderUpdate(PurchaseOrderCreate):
    version: int = Field(ge=1)


class PurchaseOrderView(ApiModel):
    id: str
    requirement_id: str
    order_number: str
    order_date: date
    supplier: str
    amount: int
    tender_reference: str
    notes: str
    cas_reconciled: bool
    cas_reconciled_at: datetime | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class CasReconciliationUpdate(ApiModel):
    reconciled: bool
    version: int = Field(ge=1)


class ProcurementStatusUpdate(ApiModel):
    status: str = Field(pattern=r"^(REGISTRADO|EN_ADQUISICIONES|EN_LICITACION|ADJUDICADO|OC_EMITIDA|CERRADO)$")
    closed: bool = False


class AcquisitionRequirementView(ApiModel):
    id: str
    area: str
    budget_year: int
    request_date: date
    expedient: str
    subject: str
    account_code: str
    account_name: str = ""
    department: str
    original_amount: int
    procurement_status: str
    procurement_closed: bool
    orders_total: int
    orders_pending_cas: int
    orders_reconciled_cas: int
    reservation_pending: int
    released_amount: int
    effective_commitment: int
    orders: list[PurchaseOrderView]
    updated_at: datetime


class AcquisitionRequirementList(ApiModel):
    items: list[AcquisitionRequirementView]
    total: int
    page: int
    page_size: int
    original_total: int
    orders_total: int
    reservation_pending_total: int
    released_total: int
    effective_commitment_total: int


class ProcurementSummary(ApiModel):
    original_requested: int
    purchase_orders: int
    orders_pending_cas: int
    orders_reconciled_cas: int
    reservation_pending: int
    released_amount: int
    effective_commitment: int
