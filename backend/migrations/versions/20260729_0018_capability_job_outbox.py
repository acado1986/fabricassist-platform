"""Generalize analysis operations into a correlation-preserving job outbox.

Revision ID: 20260729_0018
Revises: 20260728_0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0018"
down_revision: str | None = "20260728_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analysis_job_operations",
        sa.Column(
            "correlation_id",
            sa.String(length=36),
            nullable=False,
            server_default="00000000-0000-0000-0000-000000000000",
        ),
    )
    op.alter_column("analysis_job_operations", "correlation_id", server_default=None)


def downgrade() -> None:
    op.drop_column("analysis_job_operations", "correlation_id")
