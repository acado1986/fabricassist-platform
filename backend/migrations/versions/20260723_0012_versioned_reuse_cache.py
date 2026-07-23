"""Add durable versioned evidence, plan, and rendered-result reuse records.

Revision ID: 20260723_0012
Revises: 20260723_0011
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260723_0012"
down_revision = "20260723_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scan_images", sa.Column("normalized_sha256", sa.String(64)))
    op.add_column("scan_images", sa.Column("perceptual_hash", sa.String(16)))
    op.create_index(
        "ix_scan_images_tenant_normalized_sha", "scan_images", ["tenant_id", "normalized_sha256"]
    )
    op.create_table(
        "evidence_cache_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("normalized_sha256", sa.String(64), nullable=False),
        sa.Column("perceptual_hash", sa.String(16), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("normalization_version", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("delta_payload", postgresql.JSONB(), nullable=False),
        sa.Column("source_image_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reuse_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_reused_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["source_image_id"], ["scan_images.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "tenant_id",
            "normalized_sha256",
            "role",
            "normalization_version",
            "schema_version",
            "prompt_version",
            "provider",
            "model",
            name="uq_evidence_cache_exact_versioned",
        ),
    )
    op.create_index(
        "ix_evidence_cache_tenant_phash", "evidence_cache_entries", ["tenant_id", "perceptual_hash"]
    )
    op.create_table(
        "canonical_plan_cache_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("care_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_schema_version", sa.String(64), nullable=False),
        sa.Column("proposal_schema_version", sa.String(64), nullable=False),
        sa.Column("validator_version", sa.String(64), nullable=False),
        sa.Column("product_fingerprint", sa.String(64)),
        sa.Column("reuse_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_reused_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["care_result_id"], ["care_results.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id", "signature", name="uq_canonical_plan_cache_tenant_signature"
        ),
    )
    op.create_index(
        "ix_canonical_plan_cache_tenant_result",
        "canonical_plan_cache_entries",
        ["tenant_id", "care_result_id"],
    )
    op.create_table(
        "rendered_answer_cache_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_signature", sa.String(64), nullable=False),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("template_version", sa.String(64), nullable=False),
        sa.Column("answer", postgresql.JSONB(), nullable=False),
        sa.Column("source_care_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reuse_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_reused_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["source_care_result_id"], ["care_results.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "canonical_signature",
            "language",
            "template_version",
            name="uq_render_cache_versioned",
        ),
    )


def downgrade() -> None:
    op.drop_table("rendered_answer_cache_entries")
    op.drop_index(
        "ix_canonical_plan_cache_tenant_result", table_name="canonical_plan_cache_entries"
    )
    op.drop_table("canonical_plan_cache_entries")
    op.drop_index("ix_evidence_cache_tenant_phash", table_name="evidence_cache_entries")
    op.drop_table("evidence_cache_entries")
    op.drop_index("ix_scan_images_tenant_normalized_sha", table_name="scan_images")
    op.drop_column("scan_images", "perceptual_hash")
    op.drop_column("scan_images", "normalized_sha256")
