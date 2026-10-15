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
from app.db.models import BudgetAccount, BudgetVersion, PurchaseOrder, Requirement
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
        "version": 3,
        "exported_at": utcnow().isoformat(),
        "area": area,
        "budgets": budgets,
        "requirements": [
            {
                "backup_id": r.id,
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
                "procurement_status": r.procurement_status,
                "procurement_closed": r.procurement_closed,
            }
            for r in requirements
        ],
        "purchase_orders": [
            {
                "requirement_backup_id": po.requirement_id,
                "order_number": po.order_number,
                "order_date": po.order_date.isoformat(),
                "supplier": po.supplier,
                "amount": int(po.amount),
                "tender_reference": po.tender_reference,
                "notes": po.notes,
                "cas_reconciled": po.cas_reconciled,
            }
            for po in db.execute(
                select(PurchaseOrder)
                .join(Requirement, Requirement.id == PurchaseOrder.requirement_id)
                .where(Requirement.area_id == area_row.id, Requirement.deleted_at.is_(None), PurchaseOrder.deleted_at.is_(None))
                .order_by(PurchaseOrder.order_date, PurchaseOrder.created_at)
            ).scalars()
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
    if payload.get("format") != "illapel-budget-backup" or int(payload.get("version", 0)) not in {1, 2, 3}:
        raise AppError("El formato del respaldo no es compatible.")
    if payload.get("area") != area:
        raise AppError("El respaldo no corresponde al área seleccionada.")
    area_row = get_area(db, area)
    budgets = payload.get("budgets") or []
    requirements = payload.get("requirements") or []
    purchase_orders = payload.get("purchase_orders") or []
    if not isinstance(budgets, list) or not isinstance(requirements, list) or not isinstance(purchase_orders, list):
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
    requirement_map: dict[str, str] = {}
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
        backup_id = str(item.get("backup_id") or item.get("legacy_id") or "")
        existing_id = None
        if legacy_id:
            existing_id = db.execute(select(Requirement.id).where(Requirement.legacy_id == legacy_id)).scalar_one_or_none()
        if existing_id:
            if backup_id:
                requirement_map[backup_id] = existing_id
            continue
        row = Requirement(
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
            procurement_status=str(item.get("procurement_status") or "REGISTRADO")[:30],
            procurement_closed=bool(item.get("procurement_closed", False)),
            procurement_closed_at=utcnow() if bool(item.get("procurement_closed", False)) else None,
            procurement_closed_by=user["id"] if bool(item.get("procurement_closed", False)) else None,
            created_by=user["id"],
            updated_by=user["id"],
        )
        db.add(row)
        db.flush()
        if backup_id:
            requirement_map[backup_id] = row.id
        imported += 1

    orders_imported = 0
    for item in purchase_orders:
        requirement_id = requirement_map.get(str(item.get("requirement_backup_id") or ""))
        if not requirement_id:
            continue
        try:
            order_date = date.fromisoformat(str(item["order_date"]))
            amount = int(item["amount"])
            order_number = str(item["order_number"]).strip()[:120]
            supplier = str(item["supplier"]).strip()[:250]
            if amount <= 0 or not order_number or not supplier:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        duplicate = db.execute(
            select(PurchaseOrder.id).where(
                PurchaseOrder.requirement_id == requirement_id,
                PurchaseOrder.order_number == order_number,
                PurchaseOrder.order_date == order_date,
                PurchaseOrder.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if duplicate:
            continue
        reconciled = bool(item.get("cas_reconciled", False))
        db.add(PurchaseOrder(
            requirement_id=requirement_id,
            order_number=order_number,
            order_date=order_date,
            supplier=supplier,
            amount=amount,
            tender_reference=str(item.get("tender_reference") or "")[:180],
            notes=str(item.get("notes") or "")[:5000],
            cas_reconciled=reconciled,
            cas_reconciled_at=utcnow() if reconciled else None,
            cas_reconciled_by=user["id"] if reconciled else None,
            created_by=user["id"],
            updated_by=user["id"],
        ))
        orders_imported += 1
    audit_action(
        db,
        request,
        user=user,
        action="backup.import",
        entity_type="backup",
        area=area,
        details={"years": sorted(years), "requirements_imported": imported, "purchase_orders_imported": orders_imported, "replace": replace_existing},
        event_type="backup.imported",
    )
    db.commit()
    return {"message": "Respaldo importado correctamente.", "requirements_imported": imported, "purchase_orders_imported": orders_imported}
