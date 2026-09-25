"""add granular user permissions

Revision ID: 1d2f3a4b5c6d
Revises: 8b2997af9b5f
Create Date: 2026-08-06 11:55:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "1d2f3a4b5c6d"
down_revision: Union[str, Sequence[str], None] = "8b2997af9b5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_permissions",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("permission", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "permission"),
    )
    op.create_index(
        "ix_user_permissions_permission",
        "user_permissions",
        ["permission"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_permissions_permission", table_name="user_permissions")
    op.drop_table("user_permissions")
