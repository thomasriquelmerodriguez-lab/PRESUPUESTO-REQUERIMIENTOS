from __future__ import annotations

import hashlib
from datetime import timedelta

from fastapi import Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.logging import request_id_ctx
from app.core.permissions import AREA_USER_DEFAULT_PERMISSIONS, MANAGER_DEFAULT_PERMISSIONS
from app.core.security import (
    constant_time_equal,
    ensure_aware,
    hash_password,
    random_token,
    session_expirations,
    token_digest,
    user_agent_digest,
    utcnow,
    verify_password,
)
from app.db.models import RateLimitBucket, SessionRecord, User, UserArea
from app.repositories.audit import write_security_event
from app.services.audit import client_ip

settings = get_settings()
_DUMMY_HASH = hash_password("not-a-real-user-password")


def normalize_username(username: str) -> str:
    return " ".join(username.strip().lower().split())


def _rate_key(username: str, ip: str) -> str:
    return hashlib.sha256(f"login|{normalize_username(username)}|{ip}".encode()).hexdigest()


def _check_rate_limit(db: Session, username: str, ip: str) -> None:
    now = utcnow()
    key = _rate_key(username, ip)
    bucket = db.get(RateLimitBucket, key)
    if bucket and bucket.blocked_until and ensure_aware(bucket.blocked_until) > now:
        raise AuthenticationError("No fue posible iniciar sesión. Intente nuevamente más tarde.")
    if bucket and ensure_aware(bucket.window_started_at) + timedelta(minutes=settings.login_window_minutes) <= now:
        bucket.window_started_at = now
        bucket.attempt_count = 0
        bucket.blocked_until = None


def _register_failed_attempt(db: Session, username: str, ip: str) -> None:
    now = utcnow()
    key = _rate_key(username, ip)
    bucket = db.get(RateLimitBucket, key)
    if not bucket:
        bucket = RateLimitBucket(bucket_key=key, window_started_at=now, attempt_count=0)
        db.add(bucket)
    bucket.attempt_count += 1
    if bucket.attempt_count >= settings.login_attempts:
        bucket.blocked_until = now + timedelta(minutes=settings.login_window_minutes)


def _clear_rate_limit(db: Session, username: str, ip: str) -> None:
    db.execute(delete(RateLimitBucket).where(RateLimitBucket.bucket_key == _rate_key(username, ip)))


def _effective_permissions(user: User) -> list[str]:
    assigned = {item.permission for item in user.permissions}
    if assigned:
        return sorted(assigned)
    if user.role == "budget_manager":
        return sorted(MANAGER_DEFAULT_PERMISSIONS)
    if user.role == "area_user":
        return sorted(AREA_USER_DEFAULT_PERMISSIONS)
    return []


def _session_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "areas": [membership.area.slug for membership in user.areas if membership.area.active],
        "permissions": _effective_permissions(user),
        "session_version": user.session_version,
    }


def create_session(db: Session, request: Request, response: Response, password: str, user_id: str | None = None, username: str | None = None) -> tuple[dict, str]:
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != settings.app_origin:
        raise AuthorizationError("Origen de solicitud no permitido.")
    ip = client_ip(request)
    identity_hint = user_id or username or "unknown"
    _check_rate_limit(db, identity_hint, ip)
    normalized = normalize_username(username or "")
    stmt = select(User).options(
        joinedload(User.areas).joinedload(UserArea.area),
        joinedload(User.permissions),
    )
    stmt = stmt.where(User.id == user_id) if user_id else stmt.where(User.username == normalized)
    user = db.execute(stmt).unique().scalar_one_or_none()
    valid = verify_password(user.password_hash if user else _DUMMY_HASH, password)
    now = utcnow()
    if not user or not valid or not user.active or (user.locked_until and ensure_aware(user.locked_until) > now):
        _register_failed_attempt(db, identity_hint, ip)
        if user:
            user.failed_attempts += 1
            if user.failed_attempts >= settings.login_attempts:
                user.locked_until = now + timedelta(minutes=settings.login_window_minutes)
        write_security_event(
            db,
            event_type="authentication_failed",
            severity="warning",
            username_hint=normalized or "selected-user",
            ip_address=ip,
            user_agent=request.headers.get("user-agent", "unknown"),
            request_id=request_id_ctx.get(),
            details={"generic_failure": True},
        )
        db.commit()
        raise AuthenticationError("Usuario o clave incorrectos.")

    user.failed_attempts = 0
    user.locked_until = None
    _clear_rate_limit(db, identity_hint, ip)
    raw_token = random_token(32)
    csrf_token = random_token(24)
    idle_expiry, absolute_expiry = session_expirations(
        settings.session_idle_minutes, settings.session_absolute_hours
    )
    session = SessionRecord(
        token_hash=token_digest(raw_token),
        user_id=user.id,
        csrf_hash=token_digest(csrf_token),
        user_agent_hash=user_agent_digest(request.headers.get("user-agent")),
        ip_created=ip,
        last_ip=ip,
        session_version=user.session_version,
        idle_expires_at=idle_expiry,
        absolute_expires_at=absolute_expiry,
    )
    db.add(session)
    db.commit()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        path="/",
        max_age=settings.session_absolute_hours * 3600,
    )
    return _session_user(user), csrf_token


def load_session(db: Session, request: Request) -> tuple[SessionRecord, dict]:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise AuthenticationError()
    stmt = (
        select(SessionRecord)
        .options(
            joinedload(SessionRecord.user).joinedload(User.areas).joinedload(UserArea.area),
            joinedload(SessionRecord.user).joinedload(User.permissions),
        )
        .where(SessionRecord.token_hash == token_digest(raw_token))
    )
    session = db.execute(stmt).unique().scalar_one_or_none()
    now = utcnow()
    if not session or ensure_aware(session.idle_expires_at) <= now or ensure_aware(session.absolute_expires_at) <= now:
        if session:
            db.delete(session)
            db.commit()
        raise AuthenticationError("La sesión expiró. Inicie sesión nuevamente.")
    user = session.user
    if not user.active or session.session_version != user.session_version:
        db.delete(session)
        db.commit()
        raise AuthenticationError("La sesión ya no es válida.")
    if session.user_agent_hash != user_agent_digest(request.headers.get("user-agent")):
        db.delete(session)
        write_security_event(
            db,
            event_type="session_fingerprint_mismatch",
            severity="high",
            username_hint=user.username,
            ip_address=client_ip(request),
            user_agent=request.headers.get("user-agent", "unknown"),
            request_id=request_id_ctx.get(),
            details={},
        )
        db.commit()
        raise AuthenticationError("La sesión ya no es válida.")
    if (now - ensure_aware(session.last_seen_at)).total_seconds() >= settings.session_touch_seconds:
        session.last_seen_at = now
        session.last_ip = client_ip(request)
        session.idle_expires_at = min(
            now + timedelta(minutes=settings.session_idle_minutes),
            ensure_aware(session.absolute_expires_at),
        )
        db.commit()
    return session, _session_user(user)


def validate_csrf(request: Request, session: SessionRecord) -> None:
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    if origin and origin.rstrip("/") != settings.app_origin:
        raise AuthorizationError("Origen de solicitud no permitido.")
    if not origin and referer and not referer.startswith(settings.app_origin + "/"):
        raise AuthorizationError("Origen de solicitud no permitido.")
    supplied = request.headers.get("x-csrf-token", "")
    if not supplied or not constant_time_equal(token_digest(supplied), session.csrf_hash):
        raise AuthorizationError("Token de seguridad inválido.")


def delete_session(db: Session, request: Request, response: Response) -> None:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token:
        db.execute(delete(SessionRecord).where(SessionRecord.token_hash == token_digest(raw_token)))
        db.commit()
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="strict",
    )
