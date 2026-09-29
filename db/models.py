from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.db.base import Base


def uuid_str() -> str:
    return str(uuid.uuid4())


class Area(Base):
    __tablename__ = "areas"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    slug: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    areas: Mapped[list[UserArea]] = relationship(back_populates="user", cascade="all, delete-orphan")
    permissions: Mapped[list[UserPermission]] = relationship(back_populates="user", cascade="all, delete-orphan")
    __table_args__ = (
        CheckConstraint("failed_attempts >= 0", name="ck_users_failed_attempts_nonnegative"),
        CheckConstraint("session_version >= 1", name="ck_users_session_version_positive"),
    )


class UserArea(Base):
    __tablename__ = "user_areas"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), primary_key=True)
    user: Mapped[User] = relationship(back_populates="areas")
    area: Mapped[Area] = relationship()


class UserPermission(Base):
    __tablename__ = "user_permissions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    permission: Mapped[str] = mapped_column(String(80), primary_key=True)
    user: Mapped[User] = relationship(back_populates="permissions")
    __table_args__ = (
        Index("ix_user_permissions_permission", "permission"),
    )


class SessionRecord(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ip_created: Mapped[str] = mapped_column(String(64), nullable=False)
    last_ip: Mapped[str] = mapped_column(String(64), nullable=False)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    user: Mapped[User] = relationship()


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    bucket_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        CheckConstraint("attempt_count >= 0", name="ck_rate_limit_attempt_count_nonnegative"),
    )


class BudgetPeriod(Base):
    __tablename__ = "budget_periods"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    area: Mapped[Area] = relationship()
    __table_args__ = (
        UniqueConstraint("area_id", "year", name="uq_budget_period_area_year"),
        CheckConstraint("year BETWEEN 2020 AND 2100", name="ck_budget_period_year"),
        Index("ix_budget_period_area_active_year", "area_id", "active", "year"),
    )


class BudgetVersion(Base):
    __tablename__ = "budget_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id", ondelete="RESTRICT"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    total_budget: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    area: Mapped[Area] = relationship()
    accounts: Mapped[list[BudgetAccount]] = relationship(back_populates="version", cascade="all, delete-orphan")
    __table_args__ = (
        UniqueConstraint("area_id", "year", "version_number", name="uq_budget_version_number"),
        CheckConstraint("year BETWEEN 2020 AND 2100", name="ck_budget_versions_year"),
        CheckConstraint("version_number >= 1", name="ck_budget_versions_version_positive"),
        CheckConstraint("total_budget >= 0", name="ck_budget_versions_total_nonnegative"),
        Index("ix_budget_active_area_year", "area_id", "year", "active"),
        Index(
            "uq_budget_one_active_per_area_year",
            "area_id",
            "year",
            unique=True,
            postgresql_where=text("active"),
            sqlite_where=text("active = 1"),
        ),
    )


class BudgetAccount(Base):
    __tablename__ = "budget_accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    budget_version_id: Mapped[str] = mapped_column(ForeignKey("budget_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    matrix_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    parent_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    budget: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    base_new_requirements: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    obligated_cas: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    version: Mapped[BudgetVersion] = relationship(back_populates="accounts")
    __table_args__ = (
        UniqueConstraint("budget_version_id", "code", name="uq_budget_account_code"),
        CheckConstraint("level >= 0", name="ck_budget_accounts_level_nonnegative"),
        CheckConstraint("budget >= 0", name="ck_budget_accounts_budget_nonnegative"),
        CheckConstraint("base_new_requirements >= 0", name="ck_budget_accounts_new_nonnegative"),
        CheckConstraint("obligated_cas >= 0", name="ck_budget_accounts_cas_nonnegative"),
        CheckConstraint("row_version >= 1", name="ck_budget_accounts_version_positive"),
        Index("ix_budget_account_catalog", "budget_version_id", "matrix_code", "code"),
    )


class Requirement(Base):
    __tablename__ = "requirements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    legacy_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    area_id: Mapped[str] = mapped_column(ForeignKey("areas.id", ondelete="RESTRICT"), nullable=False, index=True)
    budget_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    request_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    expedient: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(1000), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    department: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    management_area: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    account_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    included_in_base: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    lock_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    lock_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    area: Mapped[Area] = relationship()
    __table_args__ = (
        CheckConstraint("budget_year BETWEEN 2020 AND 2100", name="ck_requirements_year"),
        CheckConstraint("amount > 0", name="ck_requirements_amount_positive"),
        CheckConstraint("version >= 1", name="ck_requirements_version_positive"),
        Index("ix_requirements_filters", "area_id", "budget_year", "account_code", "request_date"),
        Index("ix_requirements_active", "area_id", "deleted_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(120), nullable=False)
    area_slug: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result: Mapped[str] = mapped_column(String(30), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(1024), nullable=False)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class SecurityEvent(Base):
    __tablename__ = "security_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    username_hint: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(1024), nullable=False)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class DomainEvent(Base):
    __tablename__ = "domain_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    area_slug: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

class ImportPreviewCache(Base):
    __tablename__ = "import_preview_cache"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    area_slug: Mapped[str] = mapped_column(String(30), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
