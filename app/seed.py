from __future__ import annotations

import hashlib
import json
from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR, get_settings
from app.core.permissions import AREA_USER_DEFAULT_PERMISSIONS, MANAGER_DEFAULT_PERMISSIONS
from app.core.security import hash_password
from app.db.models import Area, BudgetVersion, Requirement, User, UserArea, UserPermission
from app.services.accounts import hierarchy_level, matrix_code, parent_code
from app.services.budgets import create_budget_version

settings = get_settings()

AREA_DEFINITIONS = {
    "municipal": "Municipal",
    "salud": "Salud",
    "educacion": "Educación",
}


def parse_legacy_date(value: str | None) -> date:
    text = str(value or "").strip()
    if not text:
        return date(2026, 1, 1)
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    parts = text.replace("-", "/").split("/")
    if len(parts) == 3:
        try:
            day, month, year = map(int, parts)
            import calendar
            day = min(max(day, 1), calendar.monthrange(year, month)[1])
            return date(year, month, day)
        except (ValueError, TypeError):
            pass
    return date(2026, 1, 1)

USER_DEFINITIONS = [
    {
        "username": "encargado de presupuesto",
        "display_name": "Encargado de presupuesto",
        "role": "budget_manager",
        "areas": ["municipal", "salud", "educacion"],
    },
    {
        "username": "salud",
        "display_name": "Salud",
        "role": "area_user",
        "areas": ["salud"],
    },
    {
        "username": "educacion",
        "display_name": "Educación",
        "role": "area_user",
        "areas": ["educacion"],
    },
]


def seed_database(db: Session) -> None:
    areas: dict[str, Area] = {}
    for slug, name in AREA_DEFINITIONS.items():
        area = db.execute(select(Area).where(Area.slug == slug)).scalar_one_or_none()
        if not area:
            area = Area(slug=slug, name=name)
            db.add(area)
            db.flush()
        areas[slug] = area

    users: dict[str, User] = {}
    permissions_initialized = int(db.execute(select(func.count(UserPermission.user_id))).scalar_one()) > 0
    for definition in USER_DEFINITIONS:
        user = db.execute(select(User).where(User.username == definition["username"])).scalar_one_or_none()
        created_user = user is None
        if not user:
            user = User(
                username=definition["username"],
                display_name=definition["display_name"],
                role=definition["role"],
                password_hash=hash_password(settings.initial_password),
            )
            db.add(user)
            db.flush()
        users[user.username] = user
        existing = {membership.area_id for membership in user.areas}
        for slug in definition["areas"]:
            if areas[slug].id not in existing:
                db.add(UserArea(user_id=user.id, area_id=areas[slug].id))
        if created_user or not permissions_initialized:
            defaults = MANAGER_DEFAULT_PERMISSIONS if definition["role"] == "budget_manager" else AREA_USER_DEFAULT_PERMISSIONS
            existing_permissions = {item.permission for item in user.permissions}
            for permission in defaults:
                if permission not in existing_permissions:
                    db.add(UserPermission(user_id=user.id, permission=permission))
    db.flush()

    municipal = areas["municipal"]
    budget_count = db.execute(
        select(func.count(BudgetVersion.id)).where(BudgetVersion.area_id == municipal.id)
    ).scalar_one()
    if budget_count == 0:
        accounts_path = BASE_DIR / "data" / "seed" / "accounts_municipal_2026.json"
        raw_accounts = json.loads(accounts_path.read_text(encoding="utf-8"))
        accounts = [
            {
                "code": item["code"],
                "name": item["name"],
                "budget": int(item.get("budget", 0)),
                "base_new_requirements": int(item.get("preObligado", 0)),
                "obligated_cas": int(item.get("obligadoCAS", 0)),
                "obligated_cas_provided": True,
                "matrix_code": matrix_code(item["code"]),
                "parent_code": parent_code(item["code"]),
                "level": hierarchy_level(item["code"]),
            }
            for item in raw_accounts
            if int(item.get("budget", 0)) > 0
        ]
        create_budget_version(
            db,
            area_slug="municipal",
            year=2026,
            source_name="MUNICIPAL - PLANILLA REQUERIMIENTOS 2026 (3).xlsx",
            source_checksum=hashlib.sha256(accounts_path.read_bytes()).hexdigest(),
            accounts=accounts,
            user_id=users["encargado de presupuesto"].id,
            is_seed=True,
        )

    request_count = int(
        db.execute(
            select(func.count(Requirement.id)).where(Requirement.area_id == municipal.id)
        ).scalar_one()
    )
    if request_count == 0:
        requirements_path = BASE_DIR / "data" / "seed" / "requirements_municipal_2026.json"
        raw_requirements = json.loads(requirements_path.read_text(encoding="utf-8"))
        manager_id = users["encargado de presupuesto"].id
        for item in raw_requirements:
            allocation = next((a for a in item.get("allocations", []) if a.get("code")), {})
            db.add(
                Requirement(
                    legacy_id=item.get("id"),
                    area_id=municipal.id,
                    budget_year=int(item.get("budgetYear", 2026)),
                    request_date=parse_legacy_date(item.get("date")),
                    expedient=str(item.get("expedient", ""))[:120],
                    subject=str(item.get("subject", ""))[:1000],
                    amount=int(item.get("total", 0)),
                    department=str(item.get("department", ""))[:250],
                    management_area=str(item.get("managementArea", ""))[:250],
                    notes=str(item.get("notes", ""))[:5000],
                    account_code=str(allocation.get("code", ""))[:40],
                    included_in_base=bool(item.get("includedInPreObligado", True)),
                    source_file=str(item.get("importedFrom", ""))[:255] or None,
                    source_row=item.get("sourceRow"),
                    created_by=manager_id,
                    updated_by=manager_id,
                )
            )
    db.commit()


def seed_database_with_lock(db: Session) -> None:
    dialect = db.get_bind().dialect.name
    lock_id = 918_226_031
    if dialect == "postgresql":
        db.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})
    try:
        seed_database(db)
    finally:
        if dialect == "postgresql":
            db.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})
            db.commit()


def main() -> None:
    from app.db.base import SessionLocal

    with SessionLocal() as db:
        seed_database_with_lock(db)


if __name__ == "__main__":
    main()
