from __future__ import annotations

import csv
import io
from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.api.deps import CsrfUser, CurrentUser, DbDep, require_area, require_permission
from app.core.config import get_settings
from app.core.uploads import read_upload_limited
from app.schemas.budgets import (
    BudgetCatalog,
    BudgetPeriodCreate,
    BudgetPeriodView,
    BudgetVersionView,
    DashboardMetrics,
    ImportApply,
    ImportPreview,
    ObligatedCasUpdate,
)
from app.services.audit import audit_action
from app.services.budgets import (
    catalog,
    create_budget_period,
    dashboard_metrics,
    list_budget_periods,
    list_versions,
    restore_seed_version,
    update_obligated_cas,
)
from app.services.imports import apply_preview, parse_budget_file, save_preview

router = APIRouter(prefix="/budgets", tags=["budgets"])
settings = get_settings()


@router.get("/{area}/years", response_model=list[BudgetPeriodView])
def budget_years(area: str, db: DbDep, user: CurrentUser):
    require_area(user, area)
    return list_budget_periods(db, area)


@router.post("/{area}/years", response_model=BudgetPeriodView)
def add_budget_year(
    area: str,
    payload: BudgetPeriodCreate,
    request: Request,
    db: DbDep,
    user: CsrfUser,
):
    require_area(user, area)
    require_permission(user, "budgets.import")
    period = create_budget_period(
        db, area_slug=area, year=payload.year, user_id=user["id"]
    )
    audit_action(
        db,
        request,
        user=user,
        action="budget.year.create",
        entity_type="budget_period",
        entity_id=period.id,
        area=area,
        details={"year": payload.year},
        event_type="budget.year.created",
    )
    db.commit()
    return next(item for item in list_budget_periods(db, area) if item["year"] == payload.year)


@router.get("/{area}/{year}/catalog", response_model=BudgetCatalog)
def get_catalog(
    area: str,
    year: int,
    db: DbDep,
    user: CurrentUser,
    matrix: str | None = Query(default=None, max_length=40),
    q: str | None = Query(default=None, max_length=120),
):
    require_area(user, area)
    require_permission(user, "budgets.view")
    return catalog(db, area, year, matrix=matrix, search_text=q)


@router.get("/{area}/{year}/metrics", response_model=DashboardMetrics)
def get_metrics(area: str, year: int, db: DbDep, user: CurrentUser):
    require_area(user, area)
    require_permission(user, "budgets.view")
    return dashboard_metrics(db, area, year)


@router.patch("/{area}/{year}/accounts/{account_id}/obligated-cas")
def patch_obligated_cas(
    area: str,
    year: int,
    account_id: str,
    payload: ObligatedCasUpdate,
    request: Request,
    db: DbDep,
    user: CsrfUser,
):
    require_area(user, area)
    require_permission(user, "budgets.edit_cas")
    result = update_obligated_cas(
        db, area, year, account_id, payload.amount, payload.row_version
    )
    audit_action(
        db,
        request,
        user=user,
        action="budget.obligated_cas.update",
        entity_type="budget_account",
        entity_id=account_id,
        area=area,
        details={"year": year, "code": result["code"], "amount": payload.amount},
        event_type="budget.changed",
    )
    db.commit()
    return result


@router.post("/import/preview", response_model=ImportPreview)
async def preview_import(
    request: Request,
    db: DbDep,
    user: CsrfUser,
    area: str = Form(...),
    year: int = Form(...),
    file: UploadFile = File(...),
):
    require_area(user, area)
    require_permission(user, "budgets.import")
    filename, content = await read_upload_limited(
        file,
        max_bytes=settings.upload_max_bytes,
        allowed_extensions={".xlsx", ".xls", ".csv", ".txt"},
    )
    parsed = await run_in_threadpool(parse_budget_file, filename, content)
    _, response = save_preview(
        db, user_id=user["id"], area=area, year=year, parsed=parsed
    )
    audit_action(
        db,
        request,
        user=user,
        action="budget.import.preview",
        entity_type="budget_version",
        area=area,
        details={
            "year": year,
            "filename": parsed["filename"],
            "checksum": parsed["checksum"],
            "included_rows": parsed["included_rows"],
        },
    )
    db.commit()
    return response


@router.post("/import/apply")
def apply_import(payload: ImportApply, request: Request, db: DbDep, user: CsrfUser):
    require_area(user, payload.area)
    require_permission(user, "budgets.import")
    version = apply_preview(
        db,
        token=payload.token,
        user_id=user["id"],
        area=payload.area,
        year=payload.year,
    )
    audit_action(
        db,
        request,
        user=user,
        action="budget.import.apply",
        entity_type="budget_version",
        entity_id=version.id,
        area=payload.area,
        details={
            "year": payload.year,
            "source": version.source_name,
            "version": version.version_number,
        },
        event_type="budget.imported",
    )
    db.commit()
    return {"message": "Presupuesto aplicado correctamente.", "version_id": version.id}


@router.get("/{area}/versions", response_model=list[BudgetVersionView])
def versions(area: str, db: DbDep, user: CurrentUser):
    require_area(user, area)
    require_permission(user, "budgets.view")
    return list_versions(db, area)


@router.post("/{area}/{year}/restore-seed")
def restore_seed(area: str, year: int, request: Request, db: DbDep, user: CsrfUser):
    require_area(user, area)
    require_permission(user, "budgets.import")
    version = restore_seed_version(db, area, year)
    audit_action(
        db,
        request,
        user=user,
        action="budget.restore_seed",
        entity_type="budget_version",
        entity_id=version.id,
        area=area,
        details={"year": year},
        event_type="budget.changed",
    )
    db.commit()
    return {"message": "Presupuesto base restaurado."}


@router.get("/{area}/{year}/export.csv")
def export_budget(area: str, year: int, db: DbDep, user: CurrentUser):
    require_area(user, area)
    require_permission(user, "budgets.export")
    data = catalog(db, area, year)
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "CUENTA",
            "DENOMINACIÓN",
            "PRESUPUESTO VIGENTE",
            "REQUERIMIENTOS INGRESADOS",
            "PRE OBLIGADO PLANILLA (REFERENCIAL)",
            "OBLIGADO CAS",
            "DISPONIBLE PROYECTADO",
        ]
    )
    for account in data["accounts"]:
        writer.writerow(
            [
                account["code"],
                account["name"],
                account["budget"],
                account["new_requirements"],
                account["base_new_requirements"],
                account["obligated_cas"],
                account["available"],
            ]
        )
    content = "\ufeff" + output.getvalue()
    filename = f"presupuesto_{area}_{year}.csv"
    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
