"""backfill municipal 2026 obligated CAS per account

Revision ID: 4a6b8c0d2e3f
Revises: 3f5a7c9d1e2b
Create Date: 2026-08-11 10:45:00
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "4a6b8c0d2e3f"
down_revision: Union[str, Sequence[str], None] = "3f5a7c9d1e2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    areas = sa.Table("areas", metadata, autoload_with=bind)
    versions = sa.Table("budget_versions", metadata, autoload_with=bind)
    accounts = sa.Table("budget_accounts", metadata, autoload_with=bind)

    municipal_id = bind.execute(
        sa.select(areas.c.id).where(areas.c.slug == "municipal")
    ).scalar_one_or_none()
    if not municipal_id:
        return

    version_ids = list(
        bind.execute(
            sa.select(versions.c.id).where(
                versions.c.area_id == municipal_id,
                versions.c.year == 2026,
            )
        ).scalars()
    )
    if not version_ids:
        return

    data_path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "seed"
        / "obligated_cas_municipal_2026.json"
    )
    if not data_path.exists():
        return

    cas_map = json.loads(data_path.read_text(encoding="utf-8"))
    for code, raw_amount in cas_map.items():
        amount = max(0, int(raw_amount))
        if amount <= 0:
            continue
        bind.execute(
            accounts.update()
            .where(
                accounts.c.budget_version_id.in_(version_ids),
                accounts.c.code == code,
                accounts.c.obligated_cas == 0,
            )
            .values(
                obligated_cas=amount,
                row_version=accounts.c.row_version + 1,
            )
        )


def downgrade() -> None:
    # Historical accounting values and possible user edits must never be erased
    # automatically on downgrade.
    pass
