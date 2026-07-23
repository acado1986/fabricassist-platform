"""Add trusted product lookup persistence.

Revision ID: 20260723_0008
Revises: 20260723_0007
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260723_0008"
down_revision = "20260723_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("source_reference", sa.Text()),
        sa.Column("license_name", sa.String(255)),
        sa.Column("variant_data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "retrieved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
    )
    op.create_index("ix_product_profiles_tenant_id", "product_profiles", ["tenant_id"])
    op.create_table(
        "product_identifiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identifier_type", sa.String(40), nullable=False),
        sa.Column("normalized_value", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_profile_id"], ["product_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.UniqueConstraint(
            "product_profile_id", "normalized_value", name="uq_product_identifiers_profile_value"
        ),
    )
    op.create_table(
        "product_lookup_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("barcode", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("product_profile_id", postgresql.UUID(as_uuid=True)),
        sa.Column("safe_snapshot", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["product_profile_id"], ["product_profiles.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_product_lookup_runs_tenant_barcode", "product_lookup_runs", ["tenant_id", "barcode"]
    )


def downgrade() -> None:
    op.drop_table("product_lookup_runs")
    op.drop_table("product_identifiers")
    op.drop_table("product_profiles")
