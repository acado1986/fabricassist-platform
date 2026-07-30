"""Add durable conversation publication metadata.

Revision ID: 20260729_0019
Revises: 20260729_0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0019"
down_revision: str | None = "20260729_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_deletion_requests_resource_type", "deletion_requests", type_="check")
    op.create_check_constraint(
        "ck_deletion_requests_resource_type",
        "deletion_requests",
        "resource_type IN ('scan', 'garment', 'image')",
    )
    op.add_column(
        "conversation_messages",
        sa.Column(
            "dispatch_correlation_id",
            sa.String(length=36),
            nullable=False,
            server_default="00000000-0000-0000-0000-000000000000",
        ),
    )
    op.add_column(
        "conversation_messages",
        sa.Column("dispatch_published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_conversation_messages_unpublished",
        "conversation_messages",
        ["status", "dispatch_published_at", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_analysis_job_operations_unpublished",
        "analysis_job_operations",
        ["status", "published_at", "created_at"],
        unique=False,
    )
    op.alter_column("conversation_messages", "dispatch_correlation_id", server_default=None)


def downgrade() -> None:
    op.drop_index(
        "ix_analysis_job_operations_unpublished",
        table_name="analysis_job_operations",
    )
    op.drop_index("ix_conversation_messages_unpublished", table_name="conversation_messages")
    op.drop_column("conversation_messages", "dispatch_published_at")
    op.drop_column("conversation_messages", "dispatch_correlation_id")
    op.drop_constraint("ck_deletion_requests_resource_type", "deletion_requests", type_="check")
    op.create_check_constraint(
        "ck_deletion_requests_resource_type",
        "deletion_requests",
        "resource_type IN ('scan', 'garment')",
    )
