"""use structural first-order accounts for budget totals

Revision ID: 6c8d0e2f4a5b
Revises: 5b7c9d1e3f4a
Create Date: 2026-09-25
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from app.services.accounts import (
    first_order_budget_total,
    has_complete_first_order_coverage,
)

revision: str = "6c8d0e2f4a5b"
down_revision: str | Sequence[str] | None = "5b7c9d1e3f4a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    versions = bind.execute(
        sa.text("SELECT id, total_budget FROM budget_versions WHERE active = true")
    ).mappings().all()

    for version in versions:
        rows = [
            dict(row)
            for row in bind.execute(
                sa.text(
                    """
                    SELECT code, budget
                    FROM budget_accounts
                    WHERE budget_version_id = :version_id
                    ORDER BY code
                    """
                ),
                {"version_id": version["id"]},
            ).mappings()
        ]
        # Existing legacy budgets can legitimately omit item-summary rows. Do
        # not rewrite those automatically. Newly uploaded budgets use the strict
        # first-order rule at import time.
        if not rows or not has_complete_first_order_coverage(rows):
            continue
        total = first_order_budget_total(rows)
        bind.execute(
            sa.text(
                "UPDATE budget_versions SET total_budget = :total WHERE id = :version_id"
            ),
            {"total": total, "version_id": version["id"]},
        )


def downgrade() -> None:
    pass
