"""use requirement registry for availability and restore municipal 2026 CAS

Revision ID: 2e4f6a7b8c9d
Revises: 1d2f3a4b5c6d
Create Date: 2026-08-11 09:45:00
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2e4f6a7b8c9d"
down_revision: Union[str, Sequence[str], None] = "1d2f3a4b5c6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    areas = sa.Table("areas", metadata, autoload_with=bind)
    budget_versions = sa.Table("budget_versions", metadata, autoload_with=bind)
    budget_accounts = sa.Table("budget_accounts", metadata, autoload_with=bind)
    requirements = sa.Table("requirements", metadata, autoload_with=bind)

    municipal_id = bind.execute(
        sa.select(areas.c.id).where(areas.c.slug == "municipal")
    ).scalar_one_or_none()
    if not municipal_id:
        return

    version_ids = list(
        bind.execute(
            sa.select(budget_versions.c.id).where(
                budget_versions.c.area_id == municipal_id,
                budget_versions.c.year == 2026,
                sa.or_(
                    budget_versions.c.is_seed.is_(True),
                    budget_versions.c.source_name.like("%REQUERIMIENTOS%2026%"),
                ),
            )
        ).scalars()
    )

    data_path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "seed"
        / "obligated_cas_municipal_2026.json"
    )
    if version_ids and data_path.exists():
        cas_map = json.loads(data_path.read_text(encoding="utf-8"))
        for code, amount in cas_map.items():
            bind.execute(
                budget_accounts.update()
                .where(
                    budget_accounts.c.budget_version_id.in_(version_ids),
                    budget_accounts.c.code == code,
                )
                .values(
                    obligated_cas=max(0, int(amount)),
                    row_version=budget_accounts.c.row_version + 1,
                )
            )

    # Legacy imports were marked as already included in PRE OBLIGADO. From this
    # version onward the requirement registry itself is the source of truth.
    bind.execute(
        requirements.update()
        .where(
            requirements.c.area_id == municipal_id,
            requirements.c.budget_year == 2026,
            requirements.c.deleted_at.is_(None),
        )
        .values(included_in_base=False)
    )


def downgrade() -> None:
    # This migration normalizes live accounting data. Reversing the historical
    # flags or CAS values automatically could corrupt user-entered changes.
    pass
