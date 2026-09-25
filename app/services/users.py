from __future__ import annotations

import re
import unicodedata

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ConflictError, NotFoundError
from app.core.permissions import PERMISSION_CODES, PERMISSION_DEFINITIONS
from app.core.security import hash_password
from app.db.models import Area, SessionRecord, User, UserArea, UserPermission
from app.schemas.users import UserCreate, UserUpdate



_PERMISSION_DEPENDENCIES = {
    "requirements.create": {"budgets.view"},
    "requirements.edit": {"requirements.view", "budgets.view"},
    "requirements.delete": {"requirements.view"},
    "requirements.export": {"requirements.view"},
    "budgets.edit_cas": {"budgets.view"},
    "budgets.import": {"budgets.view"},
    "budgets.export": {"budgets.view"},
    "reports.generate": {"requirements.view", "budgets.view"},
}


def _expanded_permissions(permissions: list[str]) -> set[str]:
    result = set(permissions) & PERMISSION_CODES
    changed = True
    while changed:
        changed = False
        for permission in tuple(result):
            for dependency in _PERMISSION_DEPENDENCIES.get(permission, set()):
                if dependency not in result:
                    result.add(dependency)
                    changed = True
    return result

def permission_catalog() -> list[dict]:
    return [
        {
            "code": item.code,
            "label": item.label,
            "description": item.description,
            "category": item.category,
        }
        for item in PERMISSION_DEFINITIONS
    ]


def _load_user(db: Session, user_id: str) -> User:
    row = db.execute(
        select(User)
        .options(joinedload(User.areas).joinedload(UserArea.area), joinedload(User.permissions))
        .where(User.id == user_id)
    ).unique().scalar_one_or_none()
    if not row:
        raise NotFoundError("El usuario no existe.")
    return row


def user_view(user: User, current_user_id: str | None = None) -> dict:
    return {
        "id": user.id,
        "display_name": user.display_name,
        "active": user.active,
        "role": user.role,
        "areas": sorted(membership.area.slug for membership in user.areas if membership.area.active),
        "permissions": sorted(item.permission for item in user.permissions),
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "is_current_user": user.id == current_user_id,
    }


def list_users(db: Session, current_user_id: str) -> list[dict]:
    rows = list(
        db.execute(
            select(User)
            .options(joinedload(User.areas).joinedload(UserArea.area), joinedload(User.permissions))
            .order_by(User.active.desc(), User.display_name.asc())
        ).unique().scalars()
    )
    return [user_view(row, current_user_id) for row in rows]


def login_options(db: Session) -> list[dict]:
    rows = list(
        db.execute(
            select(User.id, User.display_name)
            .where(User.active.is_(True))
            .order_by(User.display_name.asc())
        ).all()
    )
    return [{"id": row.id, "display_name": row.display_name} for row in rows]


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", normalized).strip().lower()
    return " ".join(normalized.split()) or "usuario"


def _ensure_unique_display_name(db: Session, display_name: str, exclude_user_id: str | None = None) -> None:
    stmt = select(User.id).where(func.lower(User.display_name) == display_name.strip().lower())
    if exclude_user_id:
        stmt = stmt.where(User.id != exclude_user_id)
    if db.execute(stmt).scalar_one_or_none():
        raise ConflictError("Ya existe un usuario con ese nombre visible.")


def _unique_username(db: Session, display_name: str) -> str:
    base = _slug(display_name)[:70]
    candidate = base
    suffix = 2
    while db.execute(select(User.id).where(User.username == candidate)).scalar_one_or_none():
        tail = f" {suffix}"
        candidate = f"{base[:80-len(tail)]}{tail}"
        suffix += 1
    return candidate


def _areas(db: Session, slugs: list[str]) -> list[Area]:
    if not slugs:
        return []
    rows = list(db.execute(select(Area).where(Area.slug.in_(slugs), Area.active.is_(True))).scalars())
    if len(rows) != len(set(slugs)):
        raise ConflictError("Una de las áreas seleccionadas no está disponible.")
    return rows


def _replace_memberships(db: Session, user: User, area_slugs: list[str], permissions: list[str]) -> None:
    db.execute(delete(UserArea).where(UserArea.user_id == user.id))
    db.execute(delete(UserPermission).where(UserPermission.user_id == user.id))
    for area in _areas(db, area_slugs):
        db.add(UserArea(user_id=user.id, area_id=area.id))
    for permission in sorted(_expanded_permissions(permissions)):
        db.add(UserPermission(user_id=user.id, permission=permission))


def create_user(db: Session, payload: UserCreate) -> User:
    _ensure_unique_display_name(db, payload.display_name)
    user = User(
        username=_unique_username(db, payload.display_name),
        display_name=payload.display_name,
        role="custom_user",
        password_hash=hash_password(payload.password),
        active=payload.active,
    )
    db.add(user)
    db.flush()
    _replace_memberships(db, user, payload.areas, payload.permissions)
    db.flush()
    db.expire(user, ["areas", "permissions"])
    return _load_user(db, user.id)


def update_user(db: Session, user_id: str, payload: UserUpdate, current_user_id: str) -> User:
    user = _load_user(db, user_id)
    _ensure_unique_display_name(db, payload.display_name, exclude_user_id=user.id)
    current_areas = sorted(m.area.slug for m in user.areas)
    current_permissions = sorted(p.permission for p in user.permissions)
    if user.id == current_user_id:
        if not payload.active:
            raise ConflictError("No puede desactivar su propia cuenta.")
        if current_areas != sorted(payload.areas) or current_permissions != sorted(payload.permissions):
            raise ConflictError("Por seguridad, no puede modificar sus propias áreas o privilegios durante la sesión.")
    changed_security = (
        user.active != payload.active
        or current_areas != sorted(payload.areas)
        or current_permissions != sorted(payload.permissions)
    )
    user.display_name = payload.display_name
    user.active = payload.active
    _replace_memberships(db, user, payload.areas, payload.permissions)
    if changed_security:
        user.session_version += 1
        db.execute(delete(SessionRecord).where(SessionRecord.user_id == user.id))
    db.flush()
    db.expire(user, ["areas", "permissions"])
    return _load_user(db, user.id)


def reset_password(db: Session, user_id: str, password: str, current_user_id: str) -> User:
    user = _load_user(db, user_id)
    user.password_hash = hash_password(password)
    user.failed_attempts = 0
    user.locked_until = None
    user.session_version += 1
    db.execute(delete(SessionRecord).where(SessionRecord.user_id == user.id))
    db.flush()
    return _load_user(db, user.id)
