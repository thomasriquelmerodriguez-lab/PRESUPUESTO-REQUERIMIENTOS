from __future__ import annotations

from ipaddress import ip_address

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import request_id_ctx
from app.repositories.audit import emit_domain_event, write_audit


def client_ip(request: Request) -> str:
    settings = get_settings()
    peer = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for", "")
    if settings.trusted_proxy_count > 0 and forwarded:
        addresses = [item.strip() for item in forwarded.split(",") if item.strip()]
        if len(addresses) >= settings.trusted_proxy_count:
            candidate = addresses[-settings.trusted_proxy_count]
            try:
                return str(ip_address(candidate))[:64]
            except ValueError:
                pass
    try:
        return str(ip_address(peer))[:64]
    except ValueError:
        return peer[:64]


def audit_action(
    db: Session,
    request: Request,
    *,
    user: dict | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    area: str | None = None,
    result: str = "success",
    details: dict | None = None,
    event_type: str | None = None,
) -> None:
    write_audit(
        db,
        user_id=user.get("id") if user else None,
        username=user.get("display_name", "anonymous") if user else "anonymous",
        area_slug=area,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        result=result,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent", "unknown"),
        request_id=request_id_ctx.get(),
        details=details,
    )
    if event_type:
        emit_domain_event(db, area_slug=area, event_type=event_type, payload=details or {})
