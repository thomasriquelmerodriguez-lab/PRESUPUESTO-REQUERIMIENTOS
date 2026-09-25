from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models import Area, BudgetAccount, BudgetPeriod, BudgetVersion, Requirement
from app.services.accounts import apply_account_hierarchy, first_order_budget_total, matrix_code


def get_area(db: Session, slug: str) -> Area:
    area = db.execute(
        select(Area).where(Area.slug == slug, Area.active.is_(True))
    ).scalar_one_or_none()
    if not area:
        raise NotFoundError("El área solicitada no existe.")
    return area



def list_budget_periods(db: Session, area_slug: str) -> list[dict]:
    area = get_area(db, area_slug)
    periods = list(
        db.execute(
            select(BudgetPeriod)
            .where(BudgetPeriod.area_id == area.id, BudgetPeriod.active.is_(True))
            .order_by(BudgetPeriod.year.desc())
        ).scalars()
    )
    active_versions = {
        row.year: row
        for row in db.execute(
            select(BudgetVersion).where(
                BudgetVersion.area_id == area.id,
                BudgetVersion.active.is_(True),
            )
        ).scalars()
    }
    return [
        {
            "id": period.id,
            "area": area_slug,
            "year": period.year,
            "active": period.active,
            "has_budget": period.year in active_versions,
            "active_version": active_versions[period.year].version_number if period.year in active_versions else None,
            "source_name": active_versions[period.year].source_name if period.year in active_versions else None,
            "total_budget": int(active_versions[period.year].total_budget) if period.year in active_versions else 0,
            "created_at": period.created_at,
        }
        for period in periods
    ]


def create_budget_period(db: Session, *, area_slug: str, year: int, user_id: str) -> BudgetPeriod:
    area = get_area(db, area_slug)
    db.execute(select(Area.id).where(Area.id == area.id).with_for_update()).scalar_one()
    existing = db.execute(
        select(BudgetPeriod).where(
            BudgetPeriod.area_id == area.id,
            BudgetPeriod.year == year,
        )
    ).scalar_one_or_none()
    if existing:
        if not existing.active:
            existing.active = True
            db.flush()
            return existing
        raise ConflictError(f"El año presupuestario {year} ya está registrado para esta área.")
    period = BudgetPeriod(area_id=area.id, year=year, active=True, created_by=user_id)
    db.add(period)
    db.flush()
    return period


def ensure_budget_period(db: Session, *, area_id: str, year: int, user_id: str | None) -> BudgetPeriod:
    period = db.execute(
        select(BudgetPeriod).where(
            BudgetPeriod.area_id == area_id,
            BudgetPeriod.year == year,
        )
    ).scalar_one_or_none()
    if period:
        if not period.active:
            period.active = True
        return period
    period = BudgetPeriod(area_id=area_id, year=year, active=True, created_by=user_id)
    db.add(period)
    db.flush()
    return period

def active_budget_version(db: Session, area_slug: str, year: int) -> BudgetVersion:
    stmt = (
        select(BudgetVersion)
        .join(Area)
        .where(
            Area.slug == area_slug,
            BudgetVersion.year == year,
            BudgetVersion.active.is_(True),
        )
        .order_by(BudgetVersion.version_number.desc())
    )
    version = db.execute(stmt).scalar_one_or_none()
    if not version:
        raise NotFoundError(
            "No existe un presupuesto cargado para el área y año seleccionados."
        )
    return version


def requirements_by_account(
    db: Session,
    area_id: str,
    year: int,
    *,
    excluding_requirement_id: str | None = None,
) -> dict[str, int]:
    """Return every active requirement grouped by its accounting code.

    `included_in_base` is intentionally ignored. The requirement registry is now the
    source of truth for the amount consumed by new requirements, which prevents the
    legacy PRE OBLIGADO value from being deducted a second time.
    """
    stmt = (
        select(Requirement.account_code, func.coalesce(func.sum(Requirement.amount), 0))
        .where(
            Requirement.area_id == area_id,
            Requirement.budget_year == year,
            Requirement.deleted_at.is_(None),
        )
        .group_by(Requirement.account_code)
    )
    if excluding_requirement_id:
        stmt = stmt.where(Requirement.id != excluding_requirement_id)
    return {code: int(total or 0) for code, total in db.execute(stmt).all()}


def _rollup_requirements(
    accounts: list[BudgetAccount], exact_totals: dict[str, int]
) -> dict[str, int]:
    """Roll requirement amounts to every visible parent without duplicating totals."""
    by_code = {account.code: account for account in accounts}
    totals = {code: int(amount) for code, amount in exact_totals.items()}
    for account in sorted(accounts, key=lambda item: item.level, reverse=True):
        amount = totals.get(account.code, 0)
        parent = account.parent_code
        if amount and parent and parent in by_code:
            totals[parent] = totals.get(parent, 0) + amount
    return totals


def _root_accounts(accounts: list[BudgetAccount]) -> list[BudgetAccount]:
    by_code = {account.code: account for account in accounts}
    return [
        account
        for account in accounts
        if not account.parent_code or account.parent_code not in by_code
    ]


def _effective_cas_total(accounts: list[BudgetAccount]) -> int:
    """Calculate CAS once per hierarchy branch.

    Some source spreadsheets repeat an aggregate CAS value at a parent and its
    children. For a branch we take the greater of the parent's value or the sum of
    the child branches, avoiding double counting while preserving CAS stored only at
    an upper level.
    """
    by_code = {account.code: account for account in accounts}
    children: dict[str, list[str]] = defaultdict(list)
    for account in accounts:
        if account.parent_code and account.parent_code in by_code:
            children[account.parent_code].append(account.code)

    memo: dict[str, int] = {}

    def branch_total(code: str) -> int:
        if code in memo:
            return memo[code]
        account = by_code[code]
        descendants = sum(branch_total(child) for child in children.get(code, []))
        value = max(int(account.obligated_cas), descendants)
        memo[code] = value
        return value

    return sum(branch_total(account.code) for account in _root_accounts(accounts))


def catalog(
    db: Session,
    area_slug: str,
    year: int,
    *,
    matrix: str | None = None,
    search_text: str | None = None,
) -> dict:
    version = active_budget_version(db, area_slug, year)
    area = get_area(db, area_slug)
    all_accounts = list(
        db.execute(
            select(BudgetAccount)
            .where(BudgetAccount.budget_version_id == version.id)
            .order_by(BudgetAccount.code)
        ).scalars()
    )

    exact_requirements = requirements_by_account(db, area.id, year)
    rolled_requirements = _rollup_requirements(all_accounts, exact_requirements)

    search = (search_text or "").strip().lower()
    accounts = [
        account
        for account in all_accounts
        if (not matrix or account.matrix_code == matrix)
        and (
            not search
            or search in account.code.lower()
            or search in account.name.lower()
        )
    ]

    items = []
    for account in accounts:
        direct_amount = exact_requirements.get(account.code, 0)
        requirement_amount = rolled_requirements.get(account.code, 0)
        available = (
            int(account.budget)
            - requirement_amount
            - int(account.obligated_cas)
        )
        items.append(
            {
                "id": account.id,
                "code": account.code,
                "name": account.name,
                "matrix_code": account.matrix_code,
                "parent_code": account.parent_code,
                "level": account.level,
                "budget": int(account.budget),
                # Legacy PRE OBLIGADO retained for data compatibility/reference only.
                "base_new_requirements": int(account.base_new_requirements),
                "pending_requirements": direct_amount,
                # New requirements now come only from actual requirement records.
                "new_requirements": requirement_amount,
                "obligated_cas": int(account.obligated_cas),
                "available": available,
                "row_version": account.row_version,
            }
        )

    total_requirements = sum(exact_requirements.values())
    total_obligated = _effective_cas_total(all_accounts)
    return {
        "area": area_slug,
        "year": year,
        "version_id": version.id,
        "source_name": version.source_name,
        "total_budget": int(version.total_budget),
        "total_new_requirements": total_requirements,
        "total_obligated_cas": total_obligated,
        "total_available": int(version.total_budget)
        - total_requirements
        - total_obligated,
        "accounts": items,
    }


def dashboard_metrics(db: Session, area_slug: str, year: int) -> dict:
    area = get_area(db, area_slug)
    version = active_budget_version(db, area_slug, year)
    accounts = list(
        db.execute(
            select(BudgetAccount).where(BudgetAccount.budget_version_id == version.id)
        ).scalars()
    )
    request_stats = db.execute(
        select(
            func.count(Requirement.id),
            func.coalesce(func.sum(Requirement.amount), 0),
            func.count(func.distinct(Requirement.account_code)),
        ).where(
            Requirement.area_id == area.id,
            Requirement.budget_year == year,
            Requirement.deleted_at.is_(None),
        )
    ).one()
    total_new = int(request_stats[1] or 0)
    total_obligated = _effective_cas_total(accounts)
    return {
        "area": area_slug,
        "year": year,
        "requirements_count": int(request_stats[0]),
        "requirements_amount": total_new,
        "accounts_used": int(request_stats[2]),
        "total_budget": int(version.total_budget),
        "total_new_requirements": total_new,
        "total_obligated_cas": total_obligated,
        "total_available": int(version.total_budget) - total_new - total_obligated,
    }


def update_obligated_cas(
    db: Session,
    area_slug: str,
    year: int,
    account_id: str,
    amount: int,
    row_version: int,
) -> dict:
    version = active_budget_version(db, area_slug, year)
    stmt = (
        update(BudgetAccount)
        .where(
            BudgetAccount.id == account_id,
            BudgetAccount.budget_version_id == version.id,
            BudgetAccount.row_version == row_version,
        )
        .values(
            obligated_cas=amount,
            row_version=BudgetAccount.row_version + 1,
        )
        .returning(BudgetAccount)
    )
    account = db.execute(stmt).scalar_one_or_none()
    if not account:
        exists = db.execute(
            select(BudgetAccount.id).where(
                BudgetAccount.id == account_id,
                BudgetAccount.budget_version_id == version.id,
            )
        ).scalar_one_or_none()
        if exists:
            raise ConflictError(
                "La cuenta fue modificada por otro usuario. Actualice la vista."
            )
        raise NotFoundError("La cuenta presupuestaria no existe.")
    db.flush()
    return {
        "id": account.id,
        "code": account.code,
        "obligated_cas": int(account.obligated_cas),
        "row_version": account.row_version,
    }


def available_for_account(
    db: Session,
    area_slug: str,
    year: int,
    code: str,
    excluding_requirement_id: str | None = None,
    *,
    lock: bool = False,
) -> int:
    version = active_budget_version(db, area_slug, year)
    area = get_area(db, area_slug)
    account_stmt = select(BudgetAccount).where(
        BudgetAccount.budget_version_id == version.id,
        BudgetAccount.code == code,
    )
    if lock:
        account_stmt = account_stmt.with_for_update()
    account = db.execute(account_stmt).scalar_one_or_none()
    if not account:
        raise NotFoundError(
            "La cuenta seleccionada no pertenece al presupuesto vigente."
        )

    all_accounts = list(
        db.execute(
            select(BudgetAccount).where(BudgetAccount.budget_version_id == version.id)
        ).scalars()
    )
    exact_requirements = requirements_by_account(
        db,
        area.id,
        year,
        excluding_requirement_id=excluding_requirement_id,
    )
    rolled = _rollup_requirements(all_accounts, exact_requirements)
    consumed = rolled.get(code, 0)
    return int(account.budget) - int(account.obligated_cas) - consumed


def create_budget_version(
    db: Session,
    *,
    area_slug: str,
    year: int,
    source_name: str,
    source_checksum: str,
    accounts: list[dict],
    user_id: str,
    is_seed: bool = False,
) -> BudgetVersion:
    # Normalize parent/level/matrix against the complete uploaded catalog before
    # totals are calculated. Parent summary rows therefore do not count again as
    # independent budget lines.
    accounts = apply_account_hierarchy(accounts)

    area = get_area(db, area_slug)
    db.execute(
        select(Area.id).where(Area.id == area.id).with_for_update()
    ).scalar_one()
    ensure_budget_period(db, area_id=area.id, year=year, user_id=user_id)
    current_max = int(
        db.execute(
            select(func.coalesce(func.max(BudgetVersion.version_number), 0)).where(
                BudgetVersion.area_id == area.id,
                BudgetVersion.year == year,
            )
        ).scalar_one()
        or 0
    )

    # Capture the current CAS by accounting code before deactivating the old
    # version. Budget modification spreadsheets often omit the CAS column; in
    # that case the obligation already recorded must not disappear.
    previous_active = db.execute(
        select(BudgetVersion).where(
            BudgetVersion.area_id == area.id,
            BudgetVersion.year == year,
            BudgetVersion.active.is_(True),
        )
    ).scalar_one_or_none()
    previous_cas: dict[str, int] = {}
    if previous_active:
        previous_cas = {
            code: int(amount or 0)
            for code, amount in db.execute(
                select(BudgetAccount.code, BudgetAccount.obligated_cas).where(
                    BudgetAccount.budget_version_id == previous_active.id
                )
            ).all()
        }

    db.execute(
        update(BudgetVersion)
        .where(BudgetVersion.area_id == area.id, BudgetVersion.year == year)
        .values(active=False)
    )

    # The budget total is based only on structural first-order accounts.
    # Never promote a child/subtotal into the overall total just because its
    # parent row is missing from the uploaded spreadsheet.
    total_budget = first_order_budget_total(accounts)

    version = BudgetVersion(
        area_id=area.id,
        year=year,
        version_number=current_max + 1,
        active=True,
        is_seed=is_seed,
        source_name=source_name[:255],
        source_checksum=source_checksum,
        total_budget=total_budget,
        created_by=user_id,
    )
    db.add(version)
    db.flush()
    for item in accounts:
        db.add(
            BudgetAccount(
                budget_version_id=version.id,
                code=item["code"],
                name=item["name"],
                matrix_code=item.get("matrix_code") or matrix_code(item["code"]),
                parent_code=item.get("parent_code"),
                level=int(item.get("level", 0)),
                budget=int(item.get("budget", 0)),
                # Kept for backwards-compatible imports, but not used in availability.
                base_new_requirements=int(item.get("base_new_requirements", 0)),
                obligated_cas=(
                    int(item.get("obligated_cas", 0))
                    if item.get("obligated_cas_provided", True)
                    else previous_cas.get(str(item["code"]), 0)
                ),
            )
        )
    db.flush()
    return version


def list_versions(db: Session, area_slug: str) -> list[dict]:
    area = get_area(db, area_slug)
    rows = db.execute(
        select(BudgetVersion)
        .where(BudgetVersion.area_id == area.id)
        .order_by(BudgetVersion.year.desc(), BudgetVersion.version_number.desc())
    ).scalars()
    return [
        {
            "id": row.id,
            "area": area_slug,
            "year": row.year,
            "version_number": row.version_number,
            "active": row.active,
            "is_seed": row.is_seed,
            "source_name": row.source_name,
            "total_budget": int(row.total_budget),
            "created_at": row.created_at,
        }
        for row in rows
    ]


def restore_seed_version(db: Session, area_slug: str, year: int) -> BudgetVersion:
    area = get_area(db, area_slug)
    seed = (
        db.execute(
            select(BudgetVersion)
            .where(
                BudgetVersion.area_id == area.id,
                BudgetVersion.year == year,
                BudgetVersion.is_seed.is_(True),
            )
            .order_by(BudgetVersion.version_number.asc())
        )
        .scalars()
        .first()
    )
    if not seed:
        raise NotFoundError("No existe una versión base para restaurar.")
    db.execute(
        update(BudgetVersion)
        .where(BudgetVersion.area_id == area.id, BudgetVersion.year == year)
        .values(active=False)
    )
    seed.active = True
    db.flush()
    return seed
