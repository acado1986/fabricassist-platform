"""Record the reason a durable product-lookup cache entry was invalidated.

Revision ID: 20260723_0010
Revises: 20260723_0009
"""

import sqlalchemy as sa
from alembic import op

revision = "20260723_0010"
down_revision = "20260723_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_lookup_runs", sa.Column("invalidation_reason", sa.String(100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("product_lookup_runs", "invalidation_reason")
