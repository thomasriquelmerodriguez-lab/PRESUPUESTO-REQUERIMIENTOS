from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AuditLog, DomainEvent, SecurityEvent


def write_audit(
    db: Session,
    *,
    user_id: str | None,
    username: str,
    area_slug: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    result: str,
    ip_address: str,
    user_agent: str,
    request_id: str,
    details: dict | None = None,
) -> AuditLog:
    row = AuditLog(
        user_id=user_id,
        username=username,
        area_slug=area_slug,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        result=result,
        ip_address=ip_address,
        user_agent=user_agent[:1024],
        request_id=request_id,
        details=details or {},
    )
    db.add(row)
    return row


def write_security_event(
    db: Session,
    *,
    event_type: str,
    severity: str,
    username_hint: str,
    ip_address: str,
    user_agent: str,
    request_id: str,
    details: dict | None = None,
) -> SecurityEvent:
    row = SecurityEvent(
        event_type=event_type,
        severity=severity,
        username_hint=username_hint[:120],
        ip_address=ip_address,
        user_agent=user_agent[:1024],
        request_id=request_id,
        details=details or {},
    )
    db.add(row)
    return row


def emit_domain_event(
    db: Session,
    *,
    area_slug: str | None,
    event_type: str,
    payload: dict | None = None,
) -> DomainEvent:
    row = DomainEvent(area_slug=area_slug, event_type=event_type, payload=payload or {})
    db.add(row)
    return row
