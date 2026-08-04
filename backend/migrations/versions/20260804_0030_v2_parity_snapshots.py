"""Add v2 parity execution snapshots and idempotent observation projections.

Revision ID: 20260804_0030
Revises: 20260803_0029
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260804_0030"
down_revision = "20260803_0029"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column(
        "analysis_revisions",
        sa.Column(
            "execution_snapshot", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
    )
    op.add_column(
        "garment_observations",
        sa.Column("projection_key", sa.String(length=160), nullable=False, server_default="legacy"),
    )
    op.add_column(
        "garment_observations",
        sa.Column("authority", sa.String(length=80), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "garment_observations",
        sa.Column("evidence_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "analysis_branch_results",
        sa.Column("cache_provenance", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "product_lookup_runs",
        sa.Column(
            "analysis_revision_id",
            UUID,
            sa.ForeignKey("analysis_revisions.id", ondelete="SET NULL"),
        ),
    )
    op.create_unique_constraint(
        "uq_garment_observations_revision_projection",
        "garment_observations",
        ["analysis_revision_id", "projection_key"],
    )
    op.drop_constraint("ck_analysis_branch_results_name", "analysis_branch_results", type_="check")
    op.create_check_constraint(
        "ck_analysis_branch_results_name",
        "analysis_branch_results",
        "branch_name IN ('garment_inspection', 'label_extraction', 'stain_treatment', "
        "'barcode_enrichment')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_analysis_branch_results_name", "analysis_branch_results", type_="check")
    op.create_check_constraint(
        "ck_analysis_branch_results_name",
        "analysis_branch_results",
        "branch_name IN ('garment_inspection', 'label_extraction', 'stain_treatment')",
    )
    op.drop_constraint(
        "uq_garment_observations_revision_projection", "garment_observations", type_="unique"
    )
    op.drop_column("garment_observations", "projection_key")
    op.drop_column("garment_observations", "authority")
    op.drop_column("garment_observations", "evidence_ids")
    op.drop_column("analysis_revisions", "execution_snapshot")
    op.drop_column("analysis_branch_results", "cache_provenance")
    op.drop_column("product_lookup_runs", "analysis_revision_id")
