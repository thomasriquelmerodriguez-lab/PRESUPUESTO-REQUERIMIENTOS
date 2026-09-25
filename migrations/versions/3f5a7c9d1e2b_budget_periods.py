"""add configurable budget periods by area

Revision ID: 3f5a7c9d1e2b
Revises: 2e4f6a7b8c9d
Create Date: 2026-08-11 10:10:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "3f5a7c9d1e2b"
down_revision: Union[str, Sequence[str], None] = "2e4f6a7b8c9d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "budget_periods",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("area_id", sa.String(length=36), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("year BETWEEN 2020 AND 2100", name="ck_budget_period_year"),
        sa.ForeignKeyConstraint(["area_id"], ["areas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("area_id", "year", name="uq_budget_period_area_year"),
    )
    op.create_index("ix_budget_periods_area_id", "budget_periods", ["area_id"], unique=False)
    op.create_index("ix_budget_periods_year", "budget_periods", ["year"], unique=False)
    op.create_index("ix_budget_periods_active", "budget_periods", ["active"], unique=False)
    op.create_index("ix_budget_period_area_active_year", "budget_periods", ["area_id", "active", "year"], unique=False)

    bind = op.get_bind()
    metadata = sa.MetaData()
    areas = sa.Table("areas", metadata, autoload_with=bind)
    versions = sa.Table("budget_versions", metadata, autoload_with=bind)
    periods = sa.Table("budget_periods", metadata, autoload_with=bind)

    rows = bind.execute(
        sa.select(versions.c.area_id, versions.c.year, sa.func.min(versions.c.created_at).label("created_at"))
        .group_by(versions.c.area_id, versions.c.year)
    ).all()
    import uuid
    for row in rows:
        bind.execute(
            periods.insert().values(
                id=str(uuid.uuid4()),
                area_id=row.area_id,
                year=row.year,
                active=True,
                created_by=None,
                created_at=row.created_at,
            )
        )


def downgrade() -> None:
    op.drop_index("ix_budget_period_area_active_year", table_name="budget_periods")
    op.drop_index("ix_budget_periods_active", table_name="budget_periods")
    op.drop_index("ix_budget_periods_year", table_name="budget_periods")
    op.drop_index("ix_budget_periods_area_id", table_name="budget_periods")
    op.drop_table("budget_periods")
