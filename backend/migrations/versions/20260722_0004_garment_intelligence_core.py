"""Breaking multi-photo evidence, planning, validation, and result cutover.

Revision ID: 20260722_0004
Revises: 20260721_0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260722_0004"
down_revision = "20260721_0003"
branch_labels = None
depends_on = None

ROLES = (
    "'garment_overview','care_label','composition_label','barcode_brand_label',"
    "'stain_closeup','damage_closeup','construction_detail','other'"
)


def upgrade() -> None:
    op.add_column(
        "model_runs",
        sa.Column("operation", sa.String(32), nullable=False, server_default="evidence"),
    )
    op.add_column("scans", sa.Column("garment_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "scans",
        sa.Column("active_analysis_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "scans", sa.Column("active_result_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.rename_table("scan_images", "scan_images_old")
    op.create_table(
        "scan_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("detected_role", sa.String(32)),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("upload_token", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("upload_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("byte_size", sa.Integer()),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("sha256", sa.String(64)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(f"role IN ({ROLES})", name="ck_scan_images_role"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
    )
    op.execute(
        "INSERT INTO scan_images (id, tenant_id, scan_id, role, object_key, upload_token, "
        "upload_expires_at, completed_at, mime_type, byte_size, width, height, sha256, created_at) "
        "SELECT id, tenant_id, scan_id, CASE kind WHEN 'garment' THEN 'garment_overview' "
        "WHEN 'care_label' THEN 'care_label' ELSE 'other' END, object_key, upload_token, "
        "upload_expires_at, completed_at, mime_type, byte_size, width, height, sha256, created_at "
        "FROM scan_images_old"
    )
    op.drop_table("scan_images_old")
    op.create_index("ix_scan_images_tenant_id", "scan_images", ["tenant_id"])
    op.create_index("ix_scan_images_scan_id", "scan_images", ["scan_id"])
    op.create_table(
        "garments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("active_analysis_revision_id", postgresql.UUID(as_uuid=True)),
        sa.Column("active_result_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_table(
        "analysis_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("garment_id", postgresql.UUID(as_uuid=True)),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("supersedes_revision_id", postgresql.UUID(as_uuid=True)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("scan_id", "revision_number", name="uq_analysis_revisions_scan_number"),
    )
    op.create_table(
        "analysis_revision_images",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("image_id", postgresql.UUID(as_uuid=True), primary_key=True),
    )
    for name, columns in (
        ("garment_evidence_dossiers", ["analysis_revision_id"]),
        ("proposed_care_plans", ["analysis_revision_id"]),
        ("care_validation_reports", ["proposed_plan_id"]),
    ):
        op.create_table(
            name,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            *(sa.Column(c, postgresql.UUID(as_uuid=True), nullable=False) for c in columns),
            sa.Column("payload", postgresql.JSONB(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
    op.drop_table("rendered_answers")
    op.drop_table("care_results")
    op.drop_table("label_extractions")
    op.create_table(
        "care_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "analysis_revision_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True
        ),
        sa.Column("dossier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposed_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("validation_report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("canonical_data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "rendered_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("care_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("template_version", sa.String(50), nullable=False),
        sa.Column("answer", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint(
            "care_result_id",
            "language",
            "template_version",
            name="uq_rendered_answers_result_language_template",
        ),
    )


def downgrade() -> None:
    raise RuntimeError(
        "The breaking garment-intelligence cutover is downgrade-only for empty test databases."
    )
