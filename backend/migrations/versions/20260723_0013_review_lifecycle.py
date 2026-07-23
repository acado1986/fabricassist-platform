"""Add review, feedback, and durable privacy-lifecycle records.

Revision ID: 20260723_0013
Revises: 20260723_0012
"""
# pyright: reportUnknownParameterType=false, reportMissingTypeArgument=false, reportUnknownArgumentType=false

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260723_0013"
down_revision = "20260723_0012"
branch_labels = None
depends_on = None


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("scan_images", sa.Column("deletion_requested_at", sa.DateTime(timezone=True)))
    op.add_column("scan_images", sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.create_table(
        "review_cases",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("tenant_id", _uuid(), nullable=False),
        sa.Column("scan_id", _uuid(), nullable=False),
        sa.Column("garment_id", _uuid()),
        sa.Column("analysis_revision_id", _uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("assigned_operator_id", _uuid()),
        sa.Column("approved_result_id", _uuid()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('open', 'assigned', 'corrected', 'approved', 'closed')",
            name="ck_review_cases_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["garment_id"], ["garments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["analysis_revision_id"], ["analysis_revisions.id"]),
        sa.ForeignKeyConstraint(["assigned_operator_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_result_id"], ["care_results.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("analysis_revision_id", name="uq_review_cases_revision"),
    )
    op.create_index(
        "ix_review_cases_tenant_status_created",
        "review_cases",
        ["tenant_id", "status", "created_at"],
    )
    op.create_table(
        "evidence_corrections",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("tenant_id", _uuid(), nullable=False),
        sa.Column("review_case_id", _uuid(), nullable=False),
        sa.Column("original_revision_id", _uuid(), nullable=False),
        sa.Column("corrected_revision_id", _uuid(), nullable=False),
        sa.Column("actor_user_id", _uuid()),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("correction", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["review_case_id"], ["review_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["original_revision_id"], ["analysis_revisions.id"]),
        sa.ForeignKeyConstraint(["corrected_revision_id"], ["analysis_revisions.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_evidence_corrections_tenant_revision",
        "evidence_corrections",
        ["tenant_id", "corrected_revision_id"],
    )
    op.create_table(
        "customer_feedback",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("tenant_id", _uuid(), nullable=False),
        sa.Column("scan_id", _uuid(), nullable=False),
        sa.Column("user_id", _uuid()),
        sa.Column("rating", sa.Integer()),
        sa.Column("comment", sa.Text()),
        sa.Column("request_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_customer_feedback_tenant_scan", "customer_feedback", ["tenant_id", "scan_id"]
    )
    op.create_table(
        "deletion_requests",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("tenant_id", _uuid(), nullable=False),
        sa.Column("user_id", _uuid()),
        sa.Column("resource_type", sa.String(20), nullable=False),
        sa.Column("resource_id", _uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column(
            "requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "resource_type IN ('scan', 'garment')", name="ck_deletion_requests_resource_type"
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed')",
            name="ck_deletion_requests_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "tenant_id", "resource_type", "resource_id", name="uq_deletion_requests_resource"
        ),
    )
    op.create_index(
        "ix_deletion_requests_status_requested", "deletion_requests", ["status", "requested_at"]
    )
    op.create_table(
        "object_deletion_outbox",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("tenant_id", _uuid(), nullable=False),
        sa.Column("deletion_request_id", _uuid(), nullable=False),
        sa.Column("image_id", _uuid()),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(100)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_object_deletion_outbox_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["deletion_request_id"], ["deletion_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["image_id"], ["scan_images.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "deletion_request_id", "object_key", name="uq_object_deletion_outbox_key"
        ),
    )
    op.create_index(
        "ix_object_deletion_outbox_status_created",
        "object_deletion_outbox",
        ["status", "created_at"],
    )
    op.create_table(
        "audit_events",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("tenant_id", _uuid(), nullable=False),
        sa.Column("actor_user_id", _uuid()),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(40), nullable=False),
        sa.Column("resource_id", _uuid(), nullable=False),
        sa.Column("safe_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_events_tenant_created", "audit_events", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("object_deletion_outbox")
    op.drop_table("deletion_requests")
    op.drop_table("customer_feedback")
    op.drop_table("evidence_corrections")
    op.drop_table("review_cases")
    op.drop_column("scan_images", "deleted_at")
    op.drop_column("scan_images", "deletion_requested_at")
