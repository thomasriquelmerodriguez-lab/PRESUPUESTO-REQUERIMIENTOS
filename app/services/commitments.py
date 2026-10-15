from __future__ import annotations

from collections import defaultdict

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models import PurchaseOrder, Requirement


def order_totals_by_requirement(
    db: Session,
    requirement_ids: list[str] | None = None,
) -> dict[str, dict[str, int]]:
    filters = [PurchaseOrder.deleted_at.is_(None)]
    if requirement_ids is not None:
        if not requirement_ids:
            return {}
        filters.append(PurchaseOrder.requirement_id.in_(requirement_ids))
    rows = db.execute(
        select(
            PurchaseOrder.requirement_id,
            func.coalesce(func.sum(PurchaseOrder.amount), 0),
            func.coalesce(
                func.sum(case((PurchaseOrder.cas_reconciled.is_(False), PurchaseOrder.amount), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(case((PurchaseOrder.cas_reconciled.is_(True), PurchaseOrder.amount), else_=0)),
                0,
            ),
        )
        .where(*filters)
        .group_by(PurchaseOrder.requirement_id)
    ).all()
    return {
        requirement_id: {
            "orders_total": int(total or 0),
            "orders_pending_cas": int(pending or 0),
            "orders_reconciled_cas": int(reconciled or 0),
        }
        for requirement_id, total, pending, reconciled in rows
    }


def requirement_financials(row: Requirement, order_totals: dict[str, int] | None = None) -> dict[str, int]:
    totals = order_totals or {}
    original = int(row.amount)
    orders_total = int(totals.get("orders_total", 0))
    orders_pending_cas = int(totals.get("orders_pending_cas", 0))
    orders_reconciled_cas = int(totals.get("orders_reconciled_cas", 0))
    reservation_pending = 0 if row.procurement_closed else max(original - orders_total, 0)
    released_amount = max(original - orders_total, 0) if row.procurement_closed else 0
    # Only orders not yet represented in CAS are discounted separately. Orders
    # marked as reconciled are assumed to already be included in Obligado CAS.
    effective_commitment = reservation_pending + orders_pending_cas
    return {
        "original_amount": original,
        "orders_total": orders_total,
        "orders_pending_cas": orders_pending_cas,
        "orders_reconciled_cas": orders_reconciled_cas,
        "reservation_pending": reservation_pending,
        "released_amount": released_amount,
        "effective_commitment": effective_commitment,
    }


def commitments_by_account(
    db: Session,
    area_id: str,
    year: int,
    *,
    excluding_requirement_id: str | None = None,
) -> dict[str, int]:
    filters = [
        Requirement.area_id == area_id,
        Requirement.budget_year == year,
        Requirement.deleted_at.is_(None),
    ]
    if excluding_requirement_id:
        filters.append(Requirement.id != excluding_requirement_id)
    requirements = list(db.execute(select(Requirement).where(*filters)).scalars())
    totals = order_totals_by_requirement(db, [row.id for row in requirements])
    result: dict[str, int] = defaultdict(int)
    for row in requirements:
        result[row.account_code] += requirement_financials(row, totals.get(row.id))["effective_commitment"]
    return dict(result)


def procurement_totals(
    db: Session,
    area_id: str,
    year: int,
    *,
    account_codes: set[str] | None = None,
) -> dict[str, int]:
    requirements = list(
        db.execute(
            select(Requirement).where(
                Requirement.area_id == area_id,
                Requirement.budget_year == year,
                Requirement.deleted_at.is_(None),
            )
        ).scalars()
    )
    if account_codes is not None:
        requirements = [row for row in requirements if row.account_code in account_codes]
    totals = order_totals_by_requirement(db, [row.id for row in requirements])
    summary = {
        "original_requested": 0,
        "purchase_orders": 0,
        "orders_pending_cas": 0,
        "orders_reconciled_cas": 0,
        "reservation_pending": 0,
        "released_amount": 0,
        "effective_commitment": 0,
    }
    for row in requirements:
        values = requirement_financials(row, totals.get(row.id))
        summary["original_requested"] += values["original_amount"]
        summary["purchase_orders"] += values["orders_total"]
        summary["orders_pending_cas"] += values["orders_pending_cas"]
        summary["orders_reconciled_cas"] += values["orders_reconciled_cas"]
        summary["reservation_pending"] += values["reservation_pending"]
        summary["released_amount"] += values["released_amount"]
        summary["effective_commitment"] += values["effective_commitment"]
    return summary
