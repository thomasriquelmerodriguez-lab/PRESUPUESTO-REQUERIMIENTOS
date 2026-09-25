from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import CsrfUser, CurrentUser, DbDep, require_permission
from app.schemas.common import MessageResponse
from app.schemas.users import PasswordReset, PermissionView, UserAdminView, UserCreate, UserUpdate
from app.services.audit import audit_action
from app.services.users import create_user, list_users, permission_catalog, reset_password, update_user, user_view

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserAdminView])
def get_users(db: DbDep, user: CurrentUser):
    require_permission(user, "users.manage")
    return list_users(db, user["id"])


@router.get("/permissions", response_model=list[PermissionView])
def get_permissions(user: CurrentUser):
    require_permission(user, "users.manage")
    return permission_catalog()


@router.post("", response_model=UserAdminView, status_code=201)
def post_user(payload: UserCreate, request: Request, db: DbDep, user: CsrfUser):
    require_permission(user, "users.manage")
    created = create_user(db, payload)
    audit_action(
        db,
        request,
        user=user,
        action="user.create",
        entity_type="user",
        entity_id=created.id,
        result="success",
        details={
            "display_name": created.display_name,
            "active": created.active,
            "areas": sorted(item.area.slug for item in created.areas),
            "permissions": sorted(item.permission for item in created.permissions),
        },
        event_type="user.changed",
    )
    db.commit()
    return user_view(created, user["id"])


@router.put("/{user_id}", response_model=UserAdminView)
def put_user(user_id: str, payload: UserUpdate, request: Request, db: DbDep, user: CsrfUser):
    require_permission(user, "users.manage")
    updated = update_user(db, user_id, payload, user["id"])
    audit_action(
        db,
        request,
        user=user,
        action="user.update",
        entity_type="user",
        entity_id=updated.id,
        result="success",
        details={
            "display_name": updated.display_name,
            "active": updated.active,
            "areas": sorted(item.area.slug for item in updated.areas),
            "permissions": sorted(item.permission for item in updated.permissions),
        },
        event_type="user.changed",
    )
    db.commit()
    return user_view(updated, user["id"])


@router.patch("/{user_id}/password", response_model=MessageResponse)
def patch_password(user_id: str, payload: PasswordReset, request: Request, db: DbDep, user: CsrfUser):
    require_permission(user, "users.manage")
    changed = reset_password(db, user_id, payload.password, user["id"])
    audit_action(
        db,
        request,
        user=user,
        action="user.password.reset",
        entity_type="user",
        entity_id=changed.id,
        result="success",
        details={"display_name": changed.display_name, "sessions_revoked": True},
        event_type="user.changed",
    )
    db.commit()
    return {"message": "Clave actualizada y sesiones anteriores cerradas."}
