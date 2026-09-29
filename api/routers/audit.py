from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbDep, require_permission
from app.db.models import AuditLog, SecurityEvent

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def audit_logs(
    db: DbDep,
    user: CurrentUser,
    area: str | None = Query(default=None, max_length=30),
    action: str | None = Query(default=None, max_length=100),
    q: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    require_permission(user, "audit.view")
    filters = []
    if area:
        filters.append(AuditLog.area_slug == area)
    if action:
        filters.append(AuditLog.action == action)
    if q:
        term = f"%{q.strip().lower()}%"
        filters.append(
            func.lower(AuditLog.username).like(term)
            | func.lower(AuditLog.action).like(term)
            | func.lower(AuditLog.entity_type).like(term)
        )
    total = int(db.execute(select(func.count(AuditLog.id)).where(*filters)).scalar_one())
    rows = list(
        db.execute(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars()
    )
    return {
        "items": [
            {
                "id": row.id,
                "username": row.username,
                "area": row.area_slug,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "result": row.result,
                "ip_address": row.ip_address,
                "user_agent": row.user_agent,
                "request_id": row.request_id,
                "details": row.details,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/security-events")
def security_events(db: DbDep, user: CurrentUser, limit: int = Query(default=100, ge=1, le=500)):
    require_permission(user, "audit.view")
    rows = list(
        db.execute(
            select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(limit)
        ).scalars()
    )
    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "severity": row.severity,
            "username_hint": row.username_hint,
            "ip_address": row.ip_address,
            "user_agent": row.user_agent,
            "request_id": row.request_id,
            "details": row.details,
            "created_at": row.created_at,
        }
        for row in rows
    ]
