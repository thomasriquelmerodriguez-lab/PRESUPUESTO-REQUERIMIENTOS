"""roll up budget values through hierarchy levels

Revision ID: 7d9e1f3a5b6c
Revises: 6c8d0e2f4a5b
Create Date: 2026-09-29
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from app.services.accounts import (
    first_order_budget_total,
    has_complete_first_order_coverage,
    rollup_budget_by_hierarchy,
)

revision: str = "7d9e1f3a5b6c"
down_revision: str | Sequence[str] | None = "6c8d0e2f4a5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    version_ids = [
        row[0]
        for row in bind.execute(sa.text("SELECT id FROM budget_versions")).all()
    ]

    for version_id in version_ids:
        rows = [
            dict(row)
            for row in bind.execute(
                sa.text(
                    """
                    SELECT id, code, budget
                    FROM budget_accounts
                    WHERE budget_version_id = :version_id
                    ORDER BY code
                    """
                ),
                {"version_id": version_id},
            ).mappings()
        ]
        if not rows:
            continue

        rolled = rollup_budget_by_hierarchy(rows)
        for item in rolled:
            bind.execute(
                sa.text(
                    """
                    UPDATE budget_accounts
                    SET budget = :budget,
                        matrix_code = :matrix_code,
                        parent_code = :parent_code,
                        level = :level
                    WHERE id = :id
                    """
                ),
                {
                    "id": item["id"],
                    "budget": int(item.get("budget", 0) or 0),
                    "matrix_code": item["matrix_code"],
                    "parent_code": item.get("parent_code"),
                    "level": int(item.get("level", 0)),
                },
            )

        # Only rewrite the version total when the structural first-order rows are
        # present. Legacy versions without them keep their previously recorded
        # total, while newly imported files are always validated before apply.
        if has_complete_first_order_coverage(rolled):
            total = first_order_budget_total(rolled)
            bind.execute(
                sa.text(
                    "UPDATE budget_versions SET total_budget = :total WHERE id = :version_id"
                ),
                {"total": total, "version_id": version_id},
            )


def downgrade() -> None:
    # Parent values are derived from their children. The exact uploaded parent
    # values are not stored separately in historical rows, so downgrade is a no-op.
    pass
