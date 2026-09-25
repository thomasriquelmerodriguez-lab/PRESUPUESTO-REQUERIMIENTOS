"""recalculate budget hierarchy and root totals

Revision ID: 5b7c9d1e3f4a
Revises: 4a6b8c0d2e3f
Create Date: 2026-09-25
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from app.services.accounts import apply_account_hierarchy

revision: str = "5b7c9d1e3f4a"
down_revision: str | Sequence[str] | None = "4a6b8c0d2e3f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    version_ids = [
        row[0]
        for row in bind.execute(sa.text("SELECT id FROM budget_versions")).all()
    ]

    for version_id in version_ids:
        raw_rows = [
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
        if not raw_rows:
            continue

        resolved = apply_account_hierarchy(raw_rows)
        for item in resolved:
            bind.execute(
                sa.text(
                    """
                    UPDATE budget_accounts
                    SET matrix_code = :matrix_code,
                        parent_code = :parent_code,
                        level = :level
                    WHERE id = :id
                    """
                ),
                {
                    "id": item["id"],
                    "matrix_code": item["matrix_code"],
                    "parent_code": item.get("parent_code"),
                    "level": int(item["level"]),
                },
            )

        total_budget = sum(
            int(item.get("budget", 0) or 0)
            for item in resolved
            if int(item.get("level", 0)) == 0
        )
        bind.execute(
            sa.text(
                "UPDATE budget_versions SET total_budget = :total WHERE id = :version_id"
            ),
            {"total": total_budget, "version_id": version_id},
        )


def downgrade() -> None:
    # This migration only recalculates derived hierarchy metadata and totals.
    # Reverting would require knowing the exact previous interpretation of each
    # uploaded spreadsheet, so downgrade is intentionally a no-op.
    pass
