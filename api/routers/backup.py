from __future__ import annotations

import hashlib
import json
from datetime import date, datetime

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select, update

from app.api.deps import CsrfUser, CurrentUser, DbDep, require_area, require_permission
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import utcnow
from app.core.uploads import read_upload_limited
from app.db.models import BudgetAccount, BudgetVersion, Requirement
from app.services.accounts import hierarchy_level, matrix_code, parent_code
from app.services.audit import audit_action
from app.services.budgets import create_budget_version, get_area

router = APIRouter(prefix="/backup", tags=["backup"])
settings = get_settings()


@router.get("")
def export_backup(area: str, db: DbDep, user: CurrentUser):
    require_area(user, area)
    require_permission(user, "backups.export")
    area_row = get_area(db, area)
    versions = list(
        db.execute(
            select(BudgetVersion).where(
                BudgetVersion.area_id == area_row.id,
                BudgetVersion.active.is_(True),
            )
        ).scalars()
    )
    budgets = []
    for version in versions:
        accounts = list(
            db.execute(
                select(BudgetAccount)
                .where(BudgetAccount.budget_version_id == version.id)
                .order_by(BudgetAccount.code)
            ).scalars()
        )
        budgets.append(
            {
                "year": version.year,
                "source_name": version.source_name,
                "accounts": [
                    {
                        "code": a.code,
                        "name": a.name,
                        "budget": int(a.budget),
                        "base_new_requirements": int(a.base_new_requirements),
                        "obligated_cas": int(a.obligated_cas),
                    }
                    for a in accounts
                ],
            }
        )
    requirements = list(
        db.execute(
            select(Requirement).where(
                Requirement.area_id == area_row.id,
                Requirement.deleted_at.is_(None),
            )
        ).scalars()
    )
    data = {
        "format": "illapel-budget-backup",
        "version": 2,
        "exported_at": utcnow().isoformat(),
        "area": area,
        "budgets": budgets,
        "requirements": [
            {
                "legacy_id": r.legacy_id or r.id,
                "budget_year": r.budget_year,
                "request_date": r.request_date.isoformat(),
                "expedient": r.expedient,
                "subject": r.subject,
                "amount": int(r.amount),
                "department": r.department,
                "management_area": r.management_area,
                "notes": r.notes,
                "account_code": r.account_code,
                "included_in_base": r.included_in_base,
                "source_file": r.source_file,
                "source_row": r.source_row,
            }
            for r in requirements
        ],
    }
    filename = f"respaldo_{area}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    return JSONResponse(
        data,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
async def import_backup(
    request: Request,
    db: DbDep,
    user: CsrfUser,
    area: str = Form(...),
    replace_existing: bool = Form(False),
    file: UploadFile = File(...),
):
    require_area(user, area)
    require_permission(user, "backups.import")
    filename, content = await read_upload_limited(
        file,
        max_bytes=settings.upload_max_bytes * 4,
        allowed_extensions={".json"},
    )
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AppError("El archivo de respaldo no es válido.") from exc
    if payload.get("format") != "illapel-budget-backup" or int(payload.get("version", 0)) not in {1, 2}:
        raise AppError("El formato del respaldo no es compatible.")
    if payload.get("area") != area:
        raise AppError("El respaldo no corresponde al área seleccionada.")
    area_row = get_area(db, area)
    budgets = payload.get("budgets") or []
    requirements = payload.get("requirements") or []
    if not isinstance(budgets, list) or not isinstance(requirements, list):
        raise AppError("La estructura del respaldo no es válida.")
    years = {int(item["year"]) for item in budgets if "year" in item}
    if replace_existing and years:
        db.execute(
            update(Requirement)
            .where(
                Requirement.area_id == area_row.id,
                Requirement.budget_year.in_(years),
                Requirement.deleted_at.is_(None),
            )
            .values(deleted_at=utcnow(), updated_by=user["id"])
        )
    for budget in budgets:
        year = int(budget["year"])
        accounts = []
        for item in budget.get("accounts", []):
            code = str(item.get("code", ""))[:40]
            name = str(item.get("name", ""))[:500]
            amount = int(item.get("budget", 0))
            if not code or not name or amount <= 0:
                continue
            accounts.append(
                {
                    "code": code,
                    "name": name,
                    "budget": amount,
                    "base_new_requirements": max(0, int(item.get("base_new_requirements", 0))),
                    "obligated_cas": max(0, int(item.get("obligated_cas", 0))),
                    "obligated_cas_provided": True,
                    "matrix_code": matrix_code(code),
                    "parent_code": parent_code(code),
                    "level": hierarchy_level(code),
                }
            )
        if accounts:
            create_budget_version(
                db,
                area_slug=area,
                year=year,
                source_name=str(budget.get("source_name") or filename or "respaldo")[:255],
                source_checksum=hashlib.sha256(content + str(year).encode()).hexdigest(),
                accounts=accounts,
                user_id=user["id"],
            )
    imported = 0
    for item in requirements:
        try:
            request_date = date.fromisoformat(str(item["request_date"]))
            amount = int(item["amount"])
            year = int(item["budget_year"])
            account_code = str(item["account_code"])
            if amount <= 0 or not account_code:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        legacy_id = str(item.get("legacy_id") or "")[:100] or None
        if legacy_id and db.execute(select(Requirement.id).where(Requirement.legacy_id == legacy_id)).scalar_one_or_none():
            continue
        db.add(
            Requirement(
                legacy_id=legacy_id,
                area_id=area_row.id,
                budget_year=year,
                request_date=request_date,
                expedient=str(item.get("expedient", ""))[:120],
                subject=str(item.get("subject", ""))[:1000],
                amount=amount,
                department=str(item.get("department", ""))[:250],
                management_area=str(item.get("management_area", ""))[:250],
                notes=str(item.get("notes", ""))[:5000],
                account_code=account_code[:40],
                included_in_base=bool(item.get("included_in_base", False)),
                source_file=str(item.get("source_file") or filename or "respaldo")[:255],
                source_row=item.get("source_row"),
                created_by=user["id"],
                updated_by=user["id"],
            )
        )
        imported += 1
    audit_action(
        db,
        request,
        user=user,
        action="backup.import",
        entity_type="backup",
        area=area,
        details={"years": sorted(years), "requirements_imported": imported, "replace": replace_existing},
        event_type="backup.imported",
    )
    db.commit()
    return {"message": "Respaldo importado correctamente.", "requirements_imported": imported}
