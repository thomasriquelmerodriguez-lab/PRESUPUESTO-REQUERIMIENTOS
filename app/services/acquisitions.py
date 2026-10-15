from __future__ import annotations

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import utcnow
from app.db.models import BudgetAccount, BudgetVersion, PurchaseOrder, Requirement
from app.schemas.acquisitions import PurchaseOrderCreate, PurchaseOrderUpdate
from app.services.budgets import get_area
from app.services.commitments import order_totals_by_requirement, requirement_financials


def _orders(db: Session, requirement_id: str) -> list[PurchaseOrder]:
    return list(
        db.execute(
            select(PurchaseOrder)
            .where(PurchaseOrder.requirement_id == requirement_id, PurchaseOrder.deleted_at.is_(None))
            .order_by(PurchaseOrder.order_date.asc(), PurchaseOrder.created_at.asc())
        ).scalars()
    )


def _order_view(row: PurchaseOrder) -> dict:
    return {
        "id": row.id,
        "requirement_id": row.requirement_id,
        "order_number": row.order_number,
        "order_date": row.order_date,
        "supplier": row.supplier,
        "amount": int(row.amount),
        "tender_reference": row.tender_reference,
        "notes": row.notes,
        "cas_reconciled": row.cas_reconciled,
        "cas_reconciled_at": row.cas_reconciled_at,
        "version": row.version,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _account_name(db: Session, row: Requirement) -> str:
    value = db.execute(
        select(BudgetAccount.name)
        .join(BudgetVersion, BudgetVersion.id == BudgetAccount.budget_version_id)
        .where(
            BudgetVersion.area_id == row.area_id,
            BudgetVersion.year == row.budget_year,
            BudgetVersion.active.is_(True),
            BudgetAccount.code == row.account_code,
        )
        .limit(1)
    ).scalar_one_or_none()
    return value or ""


def acquisition_view(db: Session, row: Requirement, area_slug: str) -> dict:
    orders = _orders(db, row.id)
    totals = {
        "orders_total": sum(int(item.amount) for item in orders),
        "orders_pending_cas": sum(int(item.amount) for item in orders if not item.cas_reconciled),
        "orders_reconciled_cas": sum(int(item.amount) for item in orders if item.cas_reconciled),
    }
    financials = requirement_financials(row, totals)
    return {
        "id": row.id,
        "area": area_slug,
        "budget_year": row.budget_year,
        "request_date": row.request_date,
        "expedient": row.expedient,
        "subject": row.subject,
        "account_code": row.account_code,
        "account_name": _account_name(db, row),
        "department": row.department,
        "original_amount": int(row.amount),
        "procurement_status": row.procurement_status,
        "procurement_closed": row.procurement_closed,
        **financials,
        "orders": [_order_view(item) for item in orders],
        "updated_at": row.updated_at,
    }


def get_acquisition_requirement(db: Session, requirement_id: str, area_slug: str) -> Requirement:
    area = get_area(db, area_slug)
    row = db.execute(
        select(Requirement).where(
            Requirement.id == requirement_id,
            Requirement.area_id == area.id,
            Requirement.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if not row:
        raise NotFoundError("El requerimiento no existe.")
    return row


def list_acquisition_requirements(
    db: Session,
    *,
    area_slug: str,
    year: int | None = None,
    status: str | None = None,
    search_text: str | None = None,
    page: int = 1,
    page_size: int = 40,
) -> dict:
    area = get_area(db, area_slug)
    filters = [Requirement.area_id == area.id, Requirement.deleted_at.is_(None)]
    if year:
        filters.append(Requirement.budget_year == year)
    if status:
        filters.append(Requirement.procurement_status == status)
    if search_text:
        term = f"%{search_text.strip().lower()}%"
        filters.append(
            or_(
                func.lower(Requirement.expedient).like(term),
                func.lower(Requirement.subject).like(term),
                func.lower(Requirement.department).like(term),
                func.lower(Requirement.account_code).like(term),
            )
        )
    total = int(db.execute(select(func.count(Requirement.id)).where(*filters)).scalar_one())
    rows = list(
        db.execute(
            select(Requirement)
            .where(*filters)
            .order_by(Requirement.procurement_closed.asc(), Requirement.request_date.desc(), Requirement.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars()
    )
    items = [acquisition_view(db, row, area_slug) for row in rows]
    all_rows = list(db.execute(select(Requirement).where(*filters)).scalars())
    totals_map = order_totals_by_requirement(db, [row.id for row in all_rows])
    summary = {
        "original_total": 0,
        "orders_total": 0,
        "reservation_pending_total": 0,
        "released_total": 0,
        "effective_commitment_total": 0,
    }
    for row in all_rows:
        values = requirement_financials(row, totals_map.get(row.id))
        summary["original_total"] += values["original_amount"]
        summary["orders_total"] += values["orders_total"]
        summary["reservation_pending_total"] += values["reservation_pending"]
        summary["released_total"] += values["released_amount"]
        summary["effective_commitment_total"] += values["effective_commitment"]
    return {"items": items, "total": total, "page": page, "page_size": page_size, **summary}


def set_procurement_status(
    db: Session,
    row: Requirement,
    *,
    status: str,
    closed: bool,
    user_id: str,
) -> Requirement:
    now = utcnow()
    row.procurement_status = "CERRADO" if closed else status
    row.procurement_closed = closed
    row.procurement_closed_at = now if closed else None
    row.procurement_closed_by = user_id if closed else None
    row.updated_at = now
    row.updated_by = user_id
    row.version += 1
    db.flush()
    return row


def add_purchase_order(
    db: Session,
    row: Requirement,
    payload: PurchaseOrderCreate,
    user_id: str,
) -> PurchaseOrder:
    order = PurchaseOrder(
        requirement_id=row.id,
        order_number=payload.order_number.strip(),
        order_date=payload.order_date,
        supplier=payload.supplier.strip(),
        amount=payload.amount,
        tender_reference=payload.tender_reference.strip(),
        notes=payload.notes.strip(),
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(order)
    row.procurement_status = "CERRADO" if payload.close_requirement else "OC_EMITIDA"
    if payload.close_requirement:
        row.procurement_closed = True
        row.procurement_closed_at = utcnow()
        row.procurement_closed_by = user_id
    row.updated_by = user_id
    row.updated_at = utcnow()
    row.version += 1
    db.flush()
    return order


def update_purchase_order(
    db: Session,
    row: Requirement,
    order_id: str,
    payload: PurchaseOrderUpdate,
    user_id: str,
) -> PurchaseOrder:
    now = utcnow()
    order = db.execute(
        update(PurchaseOrder)
        .where(
            PurchaseOrder.id == order_id,
            PurchaseOrder.requirement_id == row.id,
            PurchaseOrder.deleted_at.is_(None),
            PurchaseOrder.version == payload.version,
        )
        .values(
            order_number=payload.order_number.strip(),
            order_date=payload.order_date,
            supplier=payload.supplier.strip(),
            amount=payload.amount,
            tender_reference=payload.tender_reference.strip(),
            notes=payload.notes.strip(),
            updated_by=user_id,
            updated_at=now,
            version=PurchaseOrder.version + 1,
        )
        .returning(PurchaseOrder)
    ).scalar_one_or_none()
    if not order:
        existing = db.execute(select(PurchaseOrder).where(PurchaseOrder.id == order_id)).scalar_one_or_none()
        if not existing or existing.deleted_at:
            raise NotFoundError("La orden de compra no existe.")
        raise ConflictError("La orden de compra fue modificada por otro usuario. Actualice la vista.")
    if payload.close_requirement:
        set_procurement_status(db, row, status="CERRADO", closed=True, user_id=user_id)
    else:
        row.procurement_status = "OC_EMITIDA" if not row.procurement_closed else "CERRADO"
        row.updated_by = user_id
        row.updated_at = now
        row.version += 1
    db.flush()
    return order


def reconcile_purchase_order(
    db: Session,
    row: Requirement,
    order_id: str,
    *,
    reconciled: bool,
    version: int,
    user_id: str,
) -> PurchaseOrder:
    now = utcnow()
    order = db.execute(
        update(PurchaseOrder)
        .where(
            PurchaseOrder.id == order_id,
            PurchaseOrder.requirement_id == row.id,
            PurchaseOrder.deleted_at.is_(None),
            PurchaseOrder.version == version,
        )
        .values(
            cas_reconciled=reconciled,
            cas_reconciled_at=now if reconciled else None,
            cas_reconciled_by=user_id if reconciled else None,
            updated_by=user_id,
            updated_at=now,
            version=PurchaseOrder.version + 1,
        )
        .returning(PurchaseOrder)
    ).scalar_one_or_none()
    if not order:
        raise ConflictError("La orden de compra cambió. Actualice la vista.")
    row.updated_by = user_id
    row.updated_at = now
    row.version += 1
    db.flush()
    return order


def delete_purchase_order(
    db: Session,
    row: Requirement,
    order_id: str,
    *,
    version: int,
    user_id: str,
) -> PurchaseOrder:
    now = utcnow()
    order = db.execute(
        update(PurchaseOrder)
        .where(
            PurchaseOrder.id == order_id,
            PurchaseOrder.requirement_id == row.id,
            PurchaseOrder.deleted_at.is_(None),
            PurchaseOrder.version == version,
        )
        .values(deleted_at=now, updated_at=now, updated_by=user_id, version=PurchaseOrder.version + 1)
        .returning(PurchaseOrder)
    ).scalar_one_or_none()
    if not order:
        raise ConflictError("La orden de compra cambió o ya fue eliminada.")
    row.updated_by = user_id
    row.updated_at = now
    row.version += 1
    db.flush()
    return order
