"""Add server-owned contextual conversations.

Revision ID: 20260723_0011
Revises: 20260723_0010
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260723_0011"
down_revision = "20260723_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("garment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("active_analysis_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["garment_id"], ["garments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["active_analysis_revision_id"], ["analysis_revisions.id"]),
        sa.UniqueConstraint(
            "tenant_id", "garment_id", name="uq_conversation_threads_tenant_garment"
        ),
    )
    op.create_index(
        "ix_conversation_threads_tenant_user", "conversation_threads", ["tenant_id", "user_id"]
    )
    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("garment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(255)),
        sa.Column("analysis_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("care_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actionable_claims", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("evidence_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("uncertainties", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("follow_up_questions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("validation_report", postgresql.JSONB()),
        sa.Column("error_code", sa.String(100)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_conversation_messages_role"),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'blocked', 'needs_review', 'failed')",
            name="ck_conversation_messages_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["thread_id"], ["conversation_threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["garment_id"], ["garments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_revision_id"], ["analysis_revisions.id"]),
        sa.ForeignKeyConstraint(["care_result_id"], ["care_results.id"]),
        sa.ForeignKeyConstraint(["model_run_id"], ["model_runs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "thread_id", "idempotency_key", name="uq_conversation_messages_idempotency"
        ),
    )
    op.create_index(
        "ix_conversation_messages_thread_created",
        "conversation_messages",
        ["thread_id", "created_at", "id"],
    )
    op.create_index("ix_conversation_messages_tenant_id", "conversation_messages", ["tenant_id"])
    op.create_table(
        "conversation_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("through_message_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["thread_id"], ["conversation_threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["through_message_id"], ["conversation_messages.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "thread_id", "version", name="uq_conversation_summaries_thread_version"
        ),
    )
    op.create_index(
        "ix_conversation_summaries_tenant_thread",
        "conversation_summaries",
        ["tenant_id", "thread_id"],
    )


def downgrade() -> None:
    op.drop_table("conversation_summaries")
    op.drop_table("conversation_messages")
    op.drop_table("conversation_threads")
