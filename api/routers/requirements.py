from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.api.deps import CsrfUser, CurrentUser, DbDep, require_area, require_permission
from app.schemas.requirements import (
    LockResponse,
    RequirementCreate,
    RequirementList,
    RequirementUpdate,
    RequirementView,
)
from app.services.audit import audit_action
from app.services.requirements import (
    acquire_lock,
    create_requirement,
    delete_requirement,
    get_requirement,
    list_requirements,
    release_lock,
    requirement_view,
    update_requirement,
)

router = APIRouter(prefix="/requirements", tags=["requirements"])


@router.get("", response_model=RequirementList)
def list_items(
    db: DbDep,
    user: CurrentUser,
    area: str = Query(...),
    year: int | None = Query(default=None, ge=2020, le=2100),
    matrix: str | None = Query(default=None, max_length=40),
    account: str | None = Query(default=None, max_length=40),
    q: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    require_area(user, area)
    require_permission(user, "requirements.view")
    return list_requirements(
        db,
        area_slug=area,
        year=year,
        matrix=matrix,
        account_code=account,
        search_text=q,
        page=page,
        page_size=page_size,
    )


@router.get("/{requirement_id}", response_model=RequirementView)
def get_item(requirement_id: str, area: str, db: DbDep, user: CurrentUser):
    require_area(user, area)
    require_permission(user, "requirements.view")
    return requirement_view(db, get_requirement(db, requirement_id, area))


@router.post("", response_model=RequirementView, status_code=201)
def create_item(payload: RequirementCreate, request: Request, db: DbDep, user: CsrfUser):
    require_area(user, payload.area)
    require_permission(user, "requirements.create")
    row = create_requirement(db, payload, user["id"])
    audit_action(
        db,
        request,
        user=user,
        action="requirement.create",
        entity_type="requirement",
        entity_id=row.id,
        area=payload.area,
        details={
            "year": payload.budget_year,
            "account_code": payload.account_code,
            "amount": payload.amount,
            "over_budget_override": payload.allow_over_budget,
            "over_budget_reason": payload.over_budget_reason if payload.allow_over_budget else "",
        },
        event_type="requirement.changed",
    )
    db.commit()
    db.refresh(row)
    return requirement_view(db, row)


@router.post("/{requirement_id}/lock", response_model=LockResponse)
def lock_item(requirement_id: str, area: str, request: Request, db: DbDep, user: CsrfUser):
    require_area(user, area)
    require_permission(user, "requirements.edit")
    row = acquire_lock(db, requirement_id, area, user["id"])
    audit_action(
        db,
        request,
        user=user,
        action="requirement.lock",
        entity_type="requirement",
        entity_id=row.id,
        area=area,
        details={"expires_at": row.lock_expires_at.isoformat()},
    )
    db.commit()
    return {
        "acquired": True,
        "lock_expires_at": row.lock_expires_at,
        "locked_by": user["display_name"],
    }


@router.delete("/{requirement_id}/lock")
def unlock_item(requirement_id: str, area: str, request: Request, db: DbDep, user: CsrfUser):
    require_area(user, area)
    require_permission(user, "requirements.edit")
    release_lock(db, requirement_id, area, user["id"])
    audit_action(
        db,
        request,
        user=user,
        action="requirement.unlock",
        entity_type="requirement",
        entity_id=requirement_id,
        area=area,
    )
    db.commit()
    return {"message": "Bloqueo liberado."}


@router.put("/{requirement_id}", response_model=RequirementView)
def update_item(
    requirement_id: str,
    payload: RequirementUpdate,
    request: Request,
    db: DbDep,
    user: CsrfUser,
):
    require_area(user, payload.area)
    require_permission(user, "requirements.edit")
    row = update_requirement(db, requirement_id, payload, user["id"])
    audit_action(
        db,
        request,
        user=user,
        action="requirement.update",
        entity_type="requirement",
        entity_id=row.id,
        area=payload.area,
        details={
            "year": payload.budget_year,
            "account_code": payload.account_code,
            "amount": payload.amount,
            "version": row.version,
        },
        event_type="requirement.changed",
    )
    db.commit()
    db.refresh(row)
    return requirement_view(db, row)


@router.delete("/{requirement_id}")
def delete_item(
    requirement_id: str,
    area: str,
    version: int,
    request: Request,
    db: DbDep,
    user: CsrfUser,
):
    require_area(user, area)
    require_permission(user, "requirements.delete")
    row = delete_requirement(db, requirement_id, area, user["id"], version)
    audit_action(
        db,
        request,
        user=user,
        action="requirement.delete",
        entity_type="requirement",
        entity_id=row.id,
        area=area,
        details={"version": row.version},
        event_type="requirement.changed",
    )
    db.commit()
    return {"message": "Requerimiento eliminado."}


@router.get("/export/csv")
def export_csv(
    db: DbDep,
    user: CurrentUser,
    area: str = Query(...),
    year: int | None = Query(default=None),
    matrix: str | None = Query(default=None),
    account: str | None = Query(default=None),
    q: str | None = Query(default=None),
):
    require_area(user, area)
    require_permission(user, "requirements.export")
    data = list_requirements(
        db,
        area_slug=area,
        year=year,
        matrix=matrix,
        account_code=account,
        search_text=q,
        page=1,
        page_size=100_000,
    )
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "AÑO",
            "FECHA",
            "EXPEDIENTE",
            "MATERIA",
            "MONTO DEL REQUERIMIENTO",
            "CUENTA",
            "DEPARTAMENTO",
            "ÁREA DE GESTIÓN",
            "OBSERVACIONES",
        ]
    )
    for item in data["items"]:
        writer.writerow(
            [
                item["budget_year"],
                item["request_date"].isoformat(),
                item["expedient"],
                item["subject"],
                item["amount"],
                item["account_code"],
                item["department"],
                item["management_area"],
                item["notes"],
            ]
        )
    return StreamingResponse(
        iter([("\ufeff" + output.getvalue()).encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="requerimientos_{area}_{year or "todos"}.csv"'},
    )
