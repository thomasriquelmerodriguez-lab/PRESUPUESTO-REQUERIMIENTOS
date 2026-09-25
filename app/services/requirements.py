from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import ensure_aware, utcnow
from app.db.models import Area, BudgetAccount, BudgetVersion, Requirement, User
from app.schemas.requirements import RequirementCreate, RequirementUpdate
from app.services.accounts import matrix_code
from app.services.budgets import active_budget_version, available_for_account, get_area

LOCK_MINUTES = 5


def _requirement_payload(
    row: Requirement,
    *,
    area_slug: str,
    account_name: str = "",
    account_matrix: str = "",
    lock_owner: str | None = None,
) -> dict:
    locked_by = None
    if (
        lock_owner
        and row.lock_user_id
        and row.lock_expires_at
        and ensure_aware(row.lock_expires_at) > utcnow()
    ):
        locked_by = lock_owner
    return {
        "id": row.id,
        "area": area_slug,
        "budget_year": row.budget_year,
        "request_date": row.request_date,
        "expedient": row.expedient,
        "subject": row.subject,
        "amount": int(row.amount),
        "department": row.department,
        "management_area": row.management_area,
        "notes": row.notes,
        "account_code": row.account_code,
        "account_name": account_name or "",
        "matrix_code": account_matrix or matrix_code(row.account_code),
        "included_in_base": row.included_in_base,
        "version": row.version,
        "locked_by": locked_by,
        "lock_expires_at": row.lock_expires_at if locked_by else None,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_requirements(
    db: Session,
    *,
    area_slug: str,
    year: int | None = None,
    matrix: str | None = None,
    account_code: str | None = None,
    search_text: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    area = get_area(db, area_slug)
    filters = [Requirement.area_id == area.id, Requirement.deleted_at.is_(None)]
    if year:
        filters.append(Requirement.budget_year == year)
    if matrix:
        matrix_codes = (
            select(BudgetAccount.code)
            .join(BudgetVersion, BudgetVersion.id == BudgetAccount.budget_version_id)
            .where(
                BudgetVersion.area_id == area.id,
                BudgetVersion.active.is_(True),
                BudgetAccount.matrix_code == matrix,
                *([BudgetVersion.year == year] if year else []),
            )
        )
        filters.append(Requirement.account_code.in_(matrix_codes))
    if account_code:
        filters.append(Requirement.account_code == account_code)
    if search_text:
        term = f"%{search_text.strip().lower()}%"
        filters.append(
            or_(
                func.lower(Requirement.expedient).like(term),
                func.lower(Requirement.subject).like(term),
                func.lower(Requirement.department).like(term),
                func.lower(Requirement.management_area).like(term),
                func.lower(Requirement.account_code).like(term),
            )
        )
    total, total_amount = db.execute(
        select(func.count(Requirement.id), func.coalesce(func.sum(Requirement.amount), 0)).where(*filters)
    ).one()
    account_name = (
        select(BudgetAccount.name)
        .join(BudgetVersion, BudgetVersion.id == BudgetAccount.budget_version_id)
        .where(
            BudgetVersion.area_id == Requirement.area_id,
            BudgetVersion.year == Requirement.budget_year,
            BudgetVersion.active.is_(True),
            BudgetAccount.code == Requirement.account_code,
        )
        .limit(1)
        .correlate(Requirement)
        .scalar_subquery()
    )
    account_matrix = (
        select(BudgetAccount.matrix_code)
        .join(BudgetVersion, BudgetVersion.id == BudgetAccount.budget_version_id)
        .where(
            BudgetVersion.area_id == Requirement.area_id,
            BudgetVersion.year == Requirement.budget_year,
            BudgetVersion.active.is_(True),
            BudgetAccount.code == Requirement.account_code,
        )
        .limit(1)
        .correlate(Requirement)
        .scalar_subquery()
    )
    lock_owner = (
        select(User.display_name)
        .where(User.id == Requirement.lock_user_id)
        .limit(1)
        .correlate(Requirement)
        .scalar_subquery()
    )
    rows = list(
        db.execute(
            select(Requirement, account_name.label("account_name"), account_matrix.label("account_matrix"), lock_owner.label("lock_owner"))
            .where(*filters)
            .order_by(Requirement.request_date.desc(), Requirement.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return {
        "items": [
            _requirement_payload(
                row,
                area_slug=area_slug,
                account_name=resolved_account_name or "",
                account_matrix=resolved_account_matrix or "",
                lock_owner=resolved_lock_owner,
            )
            for row, resolved_account_name, resolved_account_matrix, resolved_lock_owner in rows
        ],
        "total": int(total),
        "total_amount": int(total_amount or 0),
        "page": page,
        "page_size": page_size,
    }


def get_requirement(db: Session, requirement_id: str, area_slug: str) -> Requirement:
    row = db.execute(
        select(Requirement)
        .join(Area)
        .where(
            Requirement.id == requirement_id,
            Area.slug == area_slug,
            Requirement.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if not row:
        raise NotFoundError("El requerimiento no existe.")
    return row


def create_requirement(db: Session, payload: RequirementCreate, user_id: str) -> Requirement:
    area = get_area(db, payload.area)
    active_budget_version(db, payload.area, payload.budget_year)
    available = available_for_account(
        db, payload.area, payload.budget_year, payload.account_code, lock=True
    )
    if payload.amount > available and not payload.allow_over_budget:
        raise ConflictError(
            f"El monto supera el disponible de la cuenta por {payload.amount - available:,} pesos."
        )
    row = Requirement(
        area_id=area.id,
        budget_year=payload.budget_year,
        request_date=payload.request_date,
        expedient=payload.expedient,
        subject=payload.subject,
        amount=payload.amount,
        department=payload.department,
        management_area=payload.management_area,
        notes=payload.notes,
        account_code=payload.account_code,
        included_in_base=False,
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(row)
    db.flush()
    return row


def acquire_lock(db: Session, requirement_id: str, area_slug: str, user_id: str) -> Requirement:
    area = get_area(db, area_slug)
    now = utcnow()
    expires = now + timedelta(minutes=LOCK_MINUTES)
    row = db.execute(
        update(Requirement)
        .where(
            Requirement.id == requirement_id,
            Requirement.area_id == area.id,
            Requirement.deleted_at.is_(None),
            or_(
                Requirement.lock_user_id.is_(None),
                Requirement.lock_user_id == user_id,
                Requirement.lock_expires_at.is_(None),
                Requirement.lock_expires_at <= now,
            ),
        )
        .values(lock_user_id=user_id, lock_expires_at=expires)
        .returning(Requirement)
    ).scalar_one_or_none()
    if row:
        db.flush()
        return row
    existing = get_requirement(db, requirement_id, area_slug)
    owner = None
    if existing.lock_user_id:
        owner = db.execute(
            select(User.display_name).where(User.id == existing.lock_user_id)
        ).scalar_one_or_none()
    raise ConflictError(f"El registro está siendo editado por {owner or 'otro usuario'}.")


def release_lock(db: Session, requirement_id: str, area_slug: str, user_id: str) -> None:
    area = get_area(db, area_slug)
    result = db.execute(
        update(Requirement)
        .where(
            Requirement.id == requirement_id,
            Requirement.area_id == area.id,
            Requirement.deleted_at.is_(None),
            Requirement.lock_user_id == user_id,
        )
        .values(lock_user_id=None, lock_expires_at=None)
    )
    if not result.rowcount:
        get_requirement(db, requirement_id, area_slug)
    db.flush()


def update_requirement(
    db: Session,
    requirement_id: str,
    payload: RequirementUpdate,
    user_id: str,
) -> Requirement:
    area = get_area(db, payload.area)
    now = utcnow()
    available = available_for_account(
        db,
        payload.area,
        payload.budget_year,
        payload.account_code,
        excluding_requirement_id=requirement_id,
        lock=True,
    )
    if payload.amount > available and not payload.allow_over_budget:
        raise ConflictError(
            f"El monto supera el disponible de la cuenta por {payload.amount - available:,} pesos."
        )
    row = db.execute(
        update(Requirement)
        .where(
            Requirement.id == requirement_id,
            Requirement.area_id == area.id,
            Requirement.deleted_at.is_(None),
            Requirement.version == payload.version,
            Requirement.lock_user_id == user_id,
            Requirement.lock_expires_at.is_not(None),
            Requirement.lock_expires_at > now,
        )
        .values(
            budget_year=payload.budget_year,
            request_date=payload.request_date,
            expedient=payload.expedient,
            subject=payload.subject,
            amount=payload.amount,
            department=payload.department,
            management_area=payload.management_area,
            notes=payload.notes,
            account_code=payload.account_code,
            updated_by=user_id,
            version=Requirement.version + 1,
            lock_user_id=None,
            lock_expires_at=None,
            updated_at=now,
        )
        .returning(Requirement)
    ).scalar_one_or_none()
    if row:
        db.flush()
        return row
    existing = get_requirement(db, requirement_id, payload.area)
    if existing.version != payload.version:
        raise ConflictError("El registro cambió desde que comenzó la edición. Actualice la vista.")
    raise ConflictError("Debe seleccionar y bloquear el registro antes de modificarlo.")


def delete_requirement(
    db: Session,
    requirement_id: str,
    area_slug: str,
    user_id: str,
    version: int,
) -> Requirement:
    area = get_area(db, area_slug)
    now = utcnow()
    row = db.execute(
        update(Requirement)
        .where(
            Requirement.id == requirement_id,
            Requirement.area_id == area.id,
            Requirement.deleted_at.is_(None),
            Requirement.version == version,
        )
        .values(
            deleted_at=now,
            updated_at=now,
            updated_by=user_id,
            version=Requirement.version + 1,
            lock_user_id=None,
            lock_expires_at=None,
        )
        .returning(Requirement)
    ).scalar_one_or_none()
    if row:
        db.flush()
        return row
    existing = get_requirement(db, requirement_id, area_slug)
    if existing.version != version:
        raise ConflictError("El registro fue modificado por otro usuario.")
    raise ConflictError("No fue posible eliminar el registro.")

def requirement_view(db: Session, row: Requirement) -> dict:
    account_info = db.execute(
        select(BudgetAccount.name, BudgetAccount.matrix_code)
        .join(BudgetVersion, BudgetVersion.id == BudgetAccount.budget_version_id)
        .where(
            BudgetVersion.area_id == row.area_id,
            BudgetVersion.year == row.budget_year,
            BudgetVersion.active.is_(True),
            BudgetAccount.code == row.account_code,
        )
        .limit(1)
    ).one_or_none()
    account_name = account_info[0] if account_info else ""
    account_matrix = account_info[1] if account_info else ""
    lock_owner = None
    if row.lock_user_id:
        lock_owner = db.execute(
            select(User.display_name).where(User.id == row.lock_user_id)
        ).scalar_one_or_none()
    area_slug = db.execute(select(Area.slug).where(Area.id == row.area_id)).scalar_one()
    return _requirement_payload(
        row,
        area_slug=area_slug,
        account_name=account_name,
        account_matrix=account_matrix,
        lock_owner=lock_owner,
    )
