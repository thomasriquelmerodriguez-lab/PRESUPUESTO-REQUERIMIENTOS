from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.db.models import Area, BudgetAccount, BudgetPeriod, BudgetVersion, Requirement
from app.services.accounts import (
    apply_account_hierarchy,
    first_order_budget_total,
    is_budget_scope_account,
    is_first_order_account,
    matrix_code,
)


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



_MONTH_LABELS = (
    "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
)


def _children_by_code(accounts: list[BudgetAccount]) -> dict[str, list[str]]:
    codes = {account.code for account in accounts}
    children: dict[str, list[str]] = defaultdict(list)
    for account in accounts:
        if account.parent_code and account.parent_code in codes:
            children[account.parent_code].append(account.code)
    return children


def _branch_cas_by_account(accounts: list[BudgetAccount]) -> dict[str, int]:
    """Return non-duplicated CAS for every account branch.

    Parent CAS values sometimes repeat the amount contained in descendants.  A
    branch therefore uses the greater of the parent's direct CAS or the sum of
    child branches, matching the non-duplicated total used by the budget
    summary while also making the value available for each dashboard row.
    """
    by_code = {account.code: account for account in accounts}
    children = _children_by_code(accounts)
    memo: dict[str, int] = {}

    def branch_total(code: str) -> int:
        if code in memo:
            return memo[code]
        descendants = sum(branch_total(child) for child in children.get(code, []))
        memo[code] = max(int(by_code[code].obligated_cas), descendants)
        return memo[code]

    for code in by_code:
        branch_total(code)
    return memo


def _scope_codes(
    accounts: list[BudgetAccount],
    selected_code: str | None,
) -> set[str]:
    by_code = {account.code: account for account in accounts}
    if not selected_code:
        return set(by_code)
    if selected_code not in by_code:
        raise NotFoundError("La cuenta seleccionada no pertenece al presupuesto vigente.")
    children = _children_by_code(accounts)
    result: set[str] = set()
    pending = [selected_code]
    while pending:
        code = pending.pop()
        if code in result:
            continue
        result.add(code)
        pending.extend(children.get(code, []))
    return result


def _dashboard_status(committed_percent: float, available: int) -> str:
    if available < 0 or committed_percent >= 90:
        return "red"
    if committed_percent >= 75:
        return "orange"
    if committed_percent >= 50:
        return "yellow"
    return "green"


def _dashboard_account_row(
    account: BudgetAccount,
    *,
    rolled_requirements: dict[str, int],
    branch_cas: dict[str, int],
) -> dict:
    budget = int(account.budget)
    requirements = int(rolled_requirements.get(account.code, 0))
    obligated_cas = int(branch_cas.get(account.code, int(account.obligated_cas)))
    available = budget - requirements - obligated_cas
    committed = ((requirements + obligated_cas) / budget * 100) if budget > 0 else 0.0
    return {
        "code": account.code,
        "name": account.name,
        "level": account.level,
        "budget": budget,
        "requirements": requirements,
        "obligated_cas": obligated_cas,
        "available": available,
        "committed_percent": round(committed, 2),
        "status": _dashboard_status(committed, available),
    }


def decision_dashboard(
    db: Session,
    area_slug: str,
    year: int,
    *,
    matrix: str | None = None,
    account_code: str | None = None,
) -> dict:
    """Build decision-oriented indicators without double-counting hierarchy.

    Overall totals use only the active budget snapshot and the non-duplicated
    CAS total.  Requirements are sourced from the requirement registry.  When a
    matrix/account filter is selected, metrics represent that branch only.
    """
    area = get_area(db, area_slug)
    version = active_budget_version(db, area_slug, year)
    accounts = list(
        db.execute(
            select(BudgetAccount)
            .where(BudgetAccount.budget_version_id == version.id)
            .order_by(BudgetAccount.code)
        ).scalars()
    )
    accounts = [account for account in accounts if is_budget_scope_account(account.code)]
    by_code = {account.code: account for account in accounts}
    children = _children_by_code(accounts)

    selected_code = account_code or matrix
    if matrix and matrix not in by_code:
        raise NotFoundError("La cuenta matriz seleccionada no existe en el presupuesto vigente.")
    if account_code and account_code not in by_code:
        raise NotFoundError("La cuenta seleccionada no existe en el presupuesto vigente.")
    if matrix and account_code:
        matrix_scope = _scope_codes(accounts, matrix)
        if account_code not in matrix_scope:
            raise AppError(
                "La cuenta específica no pertenece a la cuenta matriz seleccionada.",
                422,
                "invalid_dashboard_scope",
            )

    scope = _scope_codes(accounts, selected_code)
    exact_requirements = requirements_by_account(db, area.id, year)
    rolled_requirements = _rollup_requirements(accounts, exact_requirements)
    branch_cas = _branch_cas_by_account(accounts)

    if selected_code:
        selected = by_code[selected_code]
        total_budget = int(selected.budget)
        total_requirements = int(rolled_requirements.get(selected_code, 0))
        total_obligated = int(branch_cas.get(selected_code, int(selected.obligated_cas)))
        scope_name = selected.name
    else:
        total_budget = int(version.total_budget)
        # Keep every active requirement in the global total, including legacy
        # requirements whose account is no longer present in the active budget.
        # Those rows are also surfaced separately as an attention warning.
        total_requirements = sum(int(amount) for amount in exact_requirements.values())
        total_obligated = _effective_cas_total(accounts)
        scope_name = None

    total_available = total_budget - total_requirements - total_obligated
    committed_percent = (
        (total_requirements + total_obligated) / total_budget * 100
        if total_budget > 0
        else 0.0
    )

    # Requirement details are read once and reused for monthly and count stats.
    requirement_rows = list(
        db.execute(
            select(Requirement.request_date, Requirement.amount, Requirement.account_code)
            .where(
                Requirement.area_id == area.id,
                Requirement.budget_year == year,
                Requirement.deleted_at.is_(None),
            )
        ).all()
    )
    scoped_requirement_rows = [
        row for row in requirement_rows if (not selected_code or row.account_code in scope)
    ]
    requirements_count = len(scoped_requirement_rows)
    accounts_used = len({row.account_code for row in scoped_requirement_rows})

    month_amounts = [0] * 12
    month_counts = [0] * 12
    for request_date, amount, _code in scoped_requirement_rows:
        if request_date:
            index = int(request_date.month) - 1
            month_amounts[index] += int(amount or 0)
            month_counts[index] += 1
    monthly = [
        {
            "month": index + 1,
            "label": _MONTH_LABELS[index],
            "requirements_count": month_counts[index],
            "requirements_amount": month_amounts[index],
        }
        for index in range(12)
    ]

    # First level overview, or the direct children of a selected branch for drill-down.
    if selected_code:
        display_codes = sorted(children.get(selected_code, [])) or [selected_code]
    else:
        display_codes = sorted(
            account.code for account in accounts if is_first_order_account(account.code)
        )
    breakdown = [
        _dashboard_account_row(
            by_code[code],
            rolled_requirements=rolled_requirements,
            branch_cas=branch_cas,
        )
        for code in display_codes
        if code in scope
    ]

    leaf_codes = [
        code for code in scope
        if code in by_code and not children.get(code) and int(by_code[code].budget) > 0
    ]
    leaf_rows = [
        _dashboard_account_row(
            by_code[code],
            rolled_requirements=rolled_requirements,
            branch_cas=branch_cas,
        )
        for code in leaf_codes
    ]
    critical_candidates = [
        row for row in leaf_rows
        if row["available"] < 0
        or row["committed_percent"] >= 75
        or row["available"] <= 5_000_000
    ]
    critical_accounts = sorted(
        critical_candidates,
        key=lambda row: (
            0 if row["available"] < 0 else 1,
            -float(row["committed_percent"]),
            int(row["available"]),
            row["code"],
        ),
    )[:12]

    exact_in_scope = {
        code: int(amount)
        for code, amount in exact_requirements.items()
        if (not selected_code or code in scope) and int(amount) > 0
    }
    top_requirement_accounts = []
    for code, amount in sorted(
        exact_in_scope.items(), key=lambda item: (-item[1], item[0])
    )[:10]:
        account = by_code.get(code)
        if account:
            row = _dashboard_account_row(
                account,
                rolled_requirements=rolled_requirements,
                branch_cas=branch_cas,
            )
            row["requirements"] = amount
            top_requirement_accounts.append(row)
        else:
            top_requirement_accounts.append(
                {
                    "code": code,
                    "name": "Cuenta no presente en el presupuesto vigente",
                    "level": 0,
                    "budget": 0,
                    "requirements": amount,
                    "obligated_cas": 0,
                    "available": -amount,
                    "committed_percent": 0.0,
                    "status": "red",
                }
            )

    mapped_codes = set(by_code)
    unmapped_rows = [row for row in requirement_rows if row.account_code not in mapped_codes]
    if selected_code:
        # Orphans cannot be safely assigned to a filtered branch.
        unmapped_rows = []

    attention = {
        "negative_balance_accounts": sum(1 for row in leaf_rows if row["available"] < 0),
        "over_90_percent_accounts": sum(1 for row in leaf_rows if row["committed_percent"] >= 90),
        "low_balance_accounts": sum(
            1 for row in leaf_rows if 0 <= row["available"] <= 5_000_000
        ),
        "unmapped_requirements_count": len(unmapped_rows),
        "unmapped_requirements_amount": sum(int(row.amount or 0) for row in unmapped_rows),
    }

    return {
        "area": area_slug,
        "year": year,
        "scope_code": selected_code,
        "scope_name": scope_name,
        "requirements_count": requirements_count,
        "accounts_used": accounts_used,
        "total_budget": total_budget,
        "total_requirements": total_requirements,
        "total_obligated_cas": total_obligated,
        "total_available": total_available,
        "committed_percent": round(committed_percent, 2),
        "breakdown": breakdown,
        "monthly": monthly,
        "critical_accounts": critical_accounts,
        "top_requirement_accounts": top_requirement_accounts,
        "attention": attention,
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



def build_replacement_snapshot(
    db: Session,
    *,
    area_slug: str,
    year: int,
    uploaded_accounts: list[dict],
) -> dict:
    """Build the next active budget as a COMPLETE replacement snapshot.

    The uploaded spreadsheet becomes the new budget for the selected area/year.
    Budget amounts from older versions are never carried forward and are never
    added to the uploaded values. Accounts absent from the new spreadsheet are
    removed from the active snapshot.

    For continuity only, CAS / legacy pre-obligado values may be preserved for
    the SAME accounting code when the uploaded spreadsheet omits those columns.
    This does not affect or accumulate the budget amount.
    """
    area = get_area(db, area_slug)
    previous = db.execute(
        select(BudgetVersion).where(
            BudgetVersion.area_id == area.id,
            BudgetVersion.year == year,
            BudgetVersion.active.is_(True),
        )
    ).scalar_one_or_none()

    existing_accounts: dict[str, dict] = {}
    if previous:
        rows = db.execute(
            select(BudgetAccount).where(BudgetAccount.budget_version_id == previous.id)
        ).scalars()
        for row in rows:
            existing_accounts[row.code] = {
                "code": row.code,
                "name": row.name,
                "budget": int(row.budget),
                "base_new_requirements": int(row.base_new_requirements),
                "obligated_cas": int(row.obligated_cas),
            }

    next_accounts: list[dict] = []
    new_count = 0
    modified_count = 0
    unchanged_uploaded_count = 0
    uploaded_status: dict[str, str] = {}
    uploaded_codes: set[str] = set()

    for uploaded in uploaded_accounts:
        code = str(uploaded["code"])
        if not is_budget_scope_account(code):
            continue
        uploaded_codes.add(code)
        old = existing_accounts.get(code)
        cas_provided = bool(uploaded.get("obligated_cas_provided", False))
        new_provided = bool(uploaded.get("base_new_requirements_provided", False))
        replacement = {
            "code": code,
            "name": str(uploaded.get("name") or (old or {}).get("name") or code),
            "budget": int(uploaded.get("budget", 0) or 0),
            "base_new_requirements": (
                int(uploaded.get("base_new_requirements", 0) or 0)
                if new_provided
                else int((old or {}).get("base_new_requirements", 0) or 0)
            ),
            "obligated_cas": (
                int(uploaded.get("obligated_cas", 0) or 0)
                if cas_provided
                else int((old or {}).get("obligated_cas", 0) or 0)
            ),
            "obligated_cas_provided": True,
            "base_new_requirements_provided": True,
        }

        if old is None:
            new_count += 1
            uploaded_status[code] = "new"
        else:
            comparable_old = (
                str(old.get("name") or ""),
                int(old.get("budget", 0) or 0),
                int(old.get("base_new_requirements", 0) or 0),
                int(old.get("obligated_cas", 0) or 0),
            )
            comparable_new = (
                replacement["name"],
                replacement["budget"],
                replacement["base_new_requirements"],
                replacement["obligated_cas"],
            )
            if comparable_old == comparable_new:
                unchanged_uploaded_count += 1
                uploaded_status[code] = "unchanged"
            else:
                modified_count += 1
                uploaded_status[code] = "modified"
        next_accounts.append(replacement)

    accounts = apply_account_hierarchy(sorted(next_accounts, key=lambda item: item["code"]))
    total_budget = first_order_budget_total(accounts)
    if total_budget <= 0:
        raise AppError(
            "El nuevo presupuesto no contiene cuentas de primer orden con monto vigente "
            "desde 215-21 en adelante. Incluya al menos una cuenta como "
            "215-21-00-000-000-000 o 215-22-00-000-000-000.",
            422,
            "missing_first_order_accounts",
        )

    removed_accounts = len(set(existing_accounts) - uploaded_codes)
    return {
        "accounts": accounts,
        "total_budget": total_budget,
        "previous_total_budget": int(previous.total_budget) if previous else 0,
        "base_version_id": previous.id if previous else None,
        "base_version_number": previous.version_number if previous else None,
        "new_accounts": new_count,
        "modified_accounts": modified_count,
        "unchanged_uploaded_accounts": unchanged_uploaded_count,
        "retained_accounts": 0,
        "removed_accounts": removed_accounts,
        "uploaded_status": uploaded_status,
    }

def delete_budget_version(db: Session, area_slug: str, version_id: str) -> dict:
    """Delete any budget version and roll back if it was active.

    Versions are immutable snapshots, so deleting a historical version does not
    modify the remaining snapshots. If the active version is deleted, the most
    recent remaining version for the same area/year becomes active. If none
    remains, the budget period stays available but without an active budget.
    """
    area = get_area(db, area_slug)
    version = db.execute(
        select(BudgetVersion).where(
            BudgetVersion.id == version_id,
            BudgetVersion.area_id == area.id,
        )
    ).scalar_one_or_none()
    if not version:
        raise NotFoundError("El presupuesto cargado no existe.")
    year = version.year
    was_active = bool(version.active)
    deleted_version_number = version.version_number
    source_name = version.source_name

    # Determine rollback target before deleting the current snapshot.
    rollback = None
    if was_active:
        rollback = (
            db.execute(
                select(BudgetVersion)
                .where(
                    BudgetVersion.area_id == area.id,
                    BudgetVersion.year == year,
                    BudgetVersion.id != version.id,
                )
                .order_by(BudgetVersion.version_number.desc())
            )
            .scalars()
            .first()
        )

    db.delete(version)
    db.flush()  # release the one-active-version constraint before rollback

    if rollback:
        rollback.active = True
        db.flush()

    return {
        "id": version_id,
        "year": year,
        "version_number": deleted_version_number,
        "source_name": source_name,
        "was_seed": bool(version.is_seed),
        "was_active": was_active,
        "restored_version": rollback.version_number if rollback else None,
        "restored_version_id": rollback.id if rollback else None,
    }

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
    # The uploaded/merged snapshot is authoritative: amounts are REPLACED by
    # accounting code, never added to the previous budget.  We only resolve the
    # hierarchy metadata here (parent/level/matrix); we do not recalculate parent
    # amounts from children because the spreadsheet already represents the current
    # budget values for every level.
    accounts = apply_account_hierarchy(
        [item for item in accounts if is_budget_scope_account(str(item.get("code") or ""))]
    )

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
