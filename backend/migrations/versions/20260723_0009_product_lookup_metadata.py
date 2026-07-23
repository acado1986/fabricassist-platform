"""Add product lookup refresh and provenance metadata."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260723_0009"
down_revision = "20260723_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_lookup_runs",
        sa.Column("request_fingerprint", sa.String(64), nullable=False, server_default=""),
    )
    op.add_column(
        "product_lookup_runs",
        sa.Column(
            "schema_version", sa.String(64), nullable=False, server_default="product-lookup-v1"
        ),
    )
    op.add_column(
        "product_lookup_runs",
        sa.Column("validated_snapshot", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.add_column("product_lookup_runs", sa.Column("refreshed_at", sa.DateTime(timezone=True)))
    op.add_column("product_lookup_runs", sa.Column("invalidated_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("product_lookup_runs", "invalidated_at")
    op.drop_column("product_lookup_runs", "refreshed_at")
    op.drop_column("product_lookup_runs", "validated_snapshot")
    op.drop_column("product_lookup_runs", "schema_version")
    op.drop_column("product_lookup_runs", "request_fingerprint")
