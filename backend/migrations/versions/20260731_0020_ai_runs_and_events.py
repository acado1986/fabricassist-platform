"""Add durable client-visible AI runs and replayable SSE events.

Revision ID: 20260731_0020
Revises: 20260729_0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260731_0020"
down_revision: str | None = "20260729_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("garments", sa.Column("display_name", sa.String(length=200), nullable=True))
    op.add_column("garments", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "ai_runs",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("scan_id", UUID, sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("parent_run_id", UUID, sa.ForeignKey("ai_runs.id", ondelete="SET NULL")),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(length=100)),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_ai_runs_status",
        ),
        sa.UniqueConstraint(
            "tenant_id", "operation", "idempotency_key", name="uq_ai_runs_idempotency"
        ),
    )
    op.create_index(
        "ix_ai_runs_tenant_user_created", "ai_runs", ["tenant_id", "user_id", "created_at"]
    )
    op.create_index("ix_ai_runs_scan_status", "ai_runs", ["scan_id", "status", "created_at"])
    op.create_table(
        "ai_run_images",
        sa.Column(
            "tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "run_id", UUID, sa.ForeignKey("ai_runs.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "image_id", UUID, sa.ForeignKey("scan_images.id", ondelete="RESTRICT"), primary_key=True
        ),
    )
    op.create_table(
        "ai_run_events",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("run_id", UUID, sa.ForeignKey("ai_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("run_id", "sequence", name="uq_ai_run_events_sequence"),
    )
    op.create_index("ix_ai_run_events_run_sequence", "ai_run_events", ["run_id", "sequence"])
    op.add_column(
        "analysis_job_operations",
        sa.Column("run_id", UUID, sa.ForeignKey("ai_runs.id", ondelete="SET NULL")),
    )
    op.add_column(
        "conversation_messages",
        sa.Column("run_id", UUID, sa.ForeignKey("ai_runs.id", ondelete="SET NULL")),
    )


def downgrade() -> None:
    op.drop_column("conversation_messages", "run_id")
    op.drop_column("analysis_job_operations", "run_id")
    op.drop_index("ix_ai_run_events_run_sequence", table_name="ai_run_events")
    op.drop_table("ai_run_events")
    op.drop_table("ai_run_images")
    op.drop_index("ix_ai_runs_scan_status", table_name="ai_runs")
    op.drop_index("ix_ai_runs_tenant_user_created", table_name="ai_runs")
    op.drop_table("ai_runs")
    op.drop_column("garments", "archived_at")
    op.drop_column("garments", "display_name")
