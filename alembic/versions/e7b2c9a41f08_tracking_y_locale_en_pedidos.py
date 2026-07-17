"""tracking y locale en pedidos

Revision ID: e7b2c9a41f08
Revises: c4a8f1d27b53
Create Date: 2026-07-15 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e7b2c9a41f08"
down_revision: str | None = "c4a8f1d27b53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders", sa.Column("locale", sa.String(length=5), nullable=False, server_default="en")
    )
    op.add_column("orders", sa.Column("tracking_number", sa.String(length=100), nullable=True))
    op.add_column("orders", sa.Column("tracking_carrier", sa.String(length=60), nullable=True))
    op.add_column("orders", sa.Column("tracking_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "tracking_url")
    op.drop_column("orders", "tracking_carrier")
    op.drop_column("orders", "tracking_number")
    op.drop_column("orders", "locale")
