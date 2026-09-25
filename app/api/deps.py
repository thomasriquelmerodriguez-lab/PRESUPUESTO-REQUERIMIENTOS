from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.exceptions import AuthorizationError
from app.db.base import get_db
from app.services.auth import load_session, validate_csrf

DbDep = Annotated[Session, Depends(get_db)]


def current_session(request: Request, db: DbDep) -> dict:
    session, user = load_session(db, request)
    request.state.session_record = session
    request.state.user = user
    return user


CurrentUser = Annotated[dict, Depends(current_session)]


def csrf_protected(request: Request, db: DbDep, user: CurrentUser) -> dict:
    validate_csrf(request, request.state.session_record)
    return user


CsrfUser = Annotated[dict, Depends(csrf_protected)]


def require_area(user: dict, area: str) -> None:
    if area not in user.get("areas", []):
        raise AuthorizationError("No tiene acceso al área indicada.")


def require_permission(user: dict, permission: str) -> None:
    if permission not in set(user.get("permissions", [])):
        raise AuthorizationError("No tiene el privilegio necesario para realizar esta acción.")


def require_manager(user: dict) -> None:
    require_permission(user, "users.manage")
