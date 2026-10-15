"""add acquisitions workflow and purchase orders

Revision ID: 9e0f2a4b6c7d
Revises: 7d9e1f3a5b6c
Create Date: 2026-10-15
"""
from alembic import op
import sqlalchemy as sa

revision = "9e0f2a4b6c7d"
down_revision = "7d9e1f3a5b6c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("requirements", sa.Column("procurement_status", sa.String(length=30), nullable=False, server_default="REGISTRADO"))
    op.add_column("requirements", sa.Column("procurement_closed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("requirements", sa.Column("procurement_closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("requirements", sa.Column("procurement_closed_by", sa.String(length=36), nullable=True))
    op.create_foreign_key("fk_requirements_procurement_closed_by_users", "requirements", "users", ["procurement_closed_by"], ["id"], ondelete="SET NULL")
    op.create_index("ix_requirements_procurement_status", "requirements", ["procurement_status"])
    op.create_index("ix_requirements_procurement_closed", "requirements", ["procurement_closed"])
    op.create_index("ix_requirements_procurement", "requirements", ["area_id", "budget_year", "procurement_status", "procurement_closed"])

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("requirement_id", sa.String(length=36), nullable=False),
        sa.Column("order_number", sa.String(length=120), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("supplier", sa.String(length=250), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("tender_reference", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("cas_reconciled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cas_reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cas_reconciled_by", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_purchase_orders_amount_positive"),
        sa.CheckConstraint("version >= 1", name="ck_purchase_orders_version_positive"),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cas_reconciled_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_purchase_orders_requirement_id", "purchase_orders", ["requirement_id"])
    op.create_index("ix_purchase_orders_order_number", "purchase_orders", ["order_number"])
    op.create_index("ix_purchase_orders_order_date", "purchase_orders", ["order_date"])
    op.create_index("ix_purchase_orders_cas_reconciled", "purchase_orders", ["cas_reconciled"])
    op.create_index("ix_purchase_orders_active_requirement", "purchase_orders", ["requirement_id", "deleted_at"])

    # Existing budget managers receive the new module automatically. Other users can
    # be granted these permissions from Usuarios y privilegios.
    op.execute("""
        INSERT INTO user_permissions (user_id, permission)
        SELECT id, 'acquisitions.view' FROM users WHERE role = 'budget_manager'
        ON CONFLICT DO NOTHING
    """)
    op.execute("""
        INSERT INTO user_permissions (user_id, permission)
        SELECT id, 'acquisitions.manage' FROM users WHERE role = 'budget_manager'
        ON CONFLICT DO NOTHING
    """)


def downgrade():
    op.execute("DELETE FROM user_permissions WHERE permission IN ('acquisitions.view','acquisitions.manage')")
    op.drop_index("ix_purchase_orders_active_requirement", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_cas_reconciled", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_order_date", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_order_number", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_requirement_id", table_name="purchase_orders")
    op.drop_table("purchase_orders")
    op.drop_index("ix_requirements_procurement", table_name="requirements")
    op.drop_index("ix_requirements_procurement_closed", table_name="requirements")
    op.drop_index("ix_requirements_procurement_status", table_name="requirements")
    op.drop_constraint("fk_requirements_procurement_closed_by_users", "requirements", type_="foreignkey")
    op.drop_column("requirements", "procurement_closed_by")
    op.drop_column("requirements", "procurement_closed_at")
    op.drop_column("requirements", "procurement_closed")
    op.drop_column("requirements", "procurement_status")
