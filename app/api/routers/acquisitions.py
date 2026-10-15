from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.api.deps import CsrfUser, CurrentUser, DbDep, require_area, require_permission
from app.schemas.acquisitions import (
    AcquisitionRequirementList,
    AcquisitionRequirementView,
    CasReconciliationUpdate,
    ProcurementStatusUpdate,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
)
from app.services.acquisitions import (
    acquisition_view,
    add_purchase_order,
    delete_purchase_order,
    get_acquisition_requirement,
    list_acquisition_requirements,
    reconcile_purchase_order,
    set_procurement_status,
    update_purchase_order,
)
from app.services.audit import audit_action

router = APIRouter(prefix="/acquisitions", tags=["acquisitions"])


@router.get("", response_model=AcquisitionRequirementList)
def list_items(
    db: DbDep,
    user: CurrentUser,
    area: str = Query(...),
    year: int | None = Query(default=None, ge=2020, le=2100),
    status: str | None = Query(default=None, max_length=30),
    q: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=40, ge=1, le=200),
):
    require_area(user, area)
    require_permission(user, "acquisitions.view")
    return list_acquisition_requirements(
        db,
        area_slug=area,
        year=year,
        status=status,
        search_text=q,
        page=page,
        page_size=page_size,
    )


@router.get("/{requirement_id}", response_model=AcquisitionRequirementView)
def get_item(requirement_id: str, area: str, db: DbDep, user: CurrentUser):
    require_area(user, area)
    require_permission(user, "acquisitions.view")
    row = get_acquisition_requirement(db, requirement_id, area)
    return acquisition_view(db, row, area)


@router.patch("/{requirement_id}/status", response_model=AcquisitionRequirementView)
def patch_status(
    requirement_id: str,
    area: str,
    payload: ProcurementStatusUpdate,
    request: Request,
    db: DbDep,
    user: CsrfUser,
):
    require_area(user, area)
    require_permission(user, "acquisitions.manage")
    row = get_acquisition_requirement(db, requirement_id, area)
    set_procurement_status(db, row, status=payload.status, closed=payload.closed, user_id=user["id"])
    audit_action(
        db,
        request,
        user=user,
        action="acquisition.status.update",
        entity_type="requirement",
        entity_id=row.id,
        area=area,
        details={"status": row.procurement_status, "closed": row.procurement_closed},
        event_type="requirement.changed",
    )
    db.commit()
    db.refresh(row)
    return acquisition_view(db, row, area)


@router.post("/{requirement_id}/orders", response_model=AcquisitionRequirementView, status_code=201)
def post_order(
    requirement_id: str,
    area: str,
    payload: PurchaseOrderCreate,
    request: Request,
    db: DbDep,
    user: CsrfUser,
):
    require_area(user, area)
    require_permission(user, "acquisitions.manage")
    row = get_acquisition_requirement(db, requirement_id, area)
    order = add_purchase_order(db, row, payload, user["id"])
    audit_action(
        db,
        request,
        user=user,
        action="purchase_order.create",
        entity_type="purchase_order",
        entity_id=order.id,
        area=area,
        details={
            "requirement_id": row.id,
            "order_number": order.order_number,
            "amount": int(order.amount),
            "close_requirement": payload.close_requirement,
        },
        event_type="requirement.changed",
    )
    db.commit()
    db.refresh(row)
    return acquisition_view(db, row, area)


@router.put("/{requirement_id}/orders/{order_id}", response_model=AcquisitionRequirementView)
def put_order(
    requirement_id: str,
    order_id: str,
    area: str,
    payload: PurchaseOrderUpdate,
    request: Request,
    db: DbDep,
    user: CsrfUser,
):
    require_area(user, area)
    require_permission(user, "acquisitions.manage")
    row = get_acquisition_requirement(db, requirement_id, area)
    order = update_purchase_order(db, row, order_id, payload, user["id"])
    audit_action(
        db,
        request,
        user=user,
        action="purchase_order.update",
        entity_type="purchase_order",
        entity_id=order.id,
        area=area,
        details={"requirement_id": row.id, "amount": int(order.amount)},
        event_type="requirement.changed",
    )
    db.commit()
    db.refresh(row)
    return acquisition_view(db, row, area)


@router.patch("/{requirement_id}/orders/{order_id}/cas", response_model=AcquisitionRequirementView)
def patch_order_cas(
    requirement_id: str,
    order_id: str,
    area: str,
    payload: CasReconciliationUpdate,
    request: Request,
    db: DbDep,
    user: CsrfUser,
):
    require_area(user, area)
    require_permission(user, "acquisitions.manage")
    row = get_acquisition_requirement(db, requirement_id, area)
    order = reconcile_purchase_order(
        db,
        row,
        order_id,
        reconciled=payload.reconciled,
        version=payload.version,
        user_id=user["id"],
    )
    audit_action(
        db,
        request,
        user=user,
        action="purchase_order.cas_reconcile" if payload.reconciled else "purchase_order.cas_unreconcile",
        entity_type="purchase_order",
        entity_id=order.id,
        area=area,
        details={"requirement_id": row.id, "amount": int(order.amount), "reconciled": payload.reconciled},
        event_type="requirement.changed",
    )
    db.commit()
    db.refresh(row)
    return acquisition_view(db, row, area)


@router.delete("/{requirement_id}/orders/{order_id}", response_model=AcquisitionRequirementView)
def delete_order(
    requirement_id: str,
    order_id: str,
    area: str,
    version: int,
    request: Request,
    db: DbDep,
    user: CsrfUser,
):
    require_area(user, area)
    require_permission(user, "acquisitions.manage")
    row = get_acquisition_requirement(db, requirement_id, area)
    order = delete_purchase_order(db, row, order_id, version=version, user_id=user["id"])
    audit_action(
        db,
        request,
        user=user,
        action="purchase_order.delete",
        entity_type="purchase_order",
        entity_id=order.id,
        area=area,
        details={"requirement_id": row.id, "amount": int(order.amount)},
        event_type="requirement.changed",
    )
    db.commit()
    db.refresh(row)
    return acquisition_view(db, row, area)
