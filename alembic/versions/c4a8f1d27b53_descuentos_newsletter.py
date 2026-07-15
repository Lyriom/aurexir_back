"""descuentos del newsletter

Revision ID: c4a8f1d27b53
Revises: ff2333de81c8
Create Date: 2026-07-15 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4a8f1d27b53"
down_revision: str | None = "ff2333de81c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "discount_codes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("percent", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_discount_codes_code"), "discount_codes", ["code"], unique=True)
    op.create_index(op.f("ix_discount_codes_email"), "discount_codes", ["email"], unique=False)
    op.add_column("orders", sa.Column("discount_code", sa.String(length=20), nullable=True))
    op.add_column(
        "orders",
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("orders", "discount_amount")
    op.drop_column("orders", "discount_code")
    op.drop_index(op.f("ix_discount_codes_email"), table_name="discount_codes")
    op.drop_index(op.f("ix_discount_codes_code"), table_name="discount_codes")
    op.drop_table("discount_codes")
