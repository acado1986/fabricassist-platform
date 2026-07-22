"""Align rendered answer timestamps with the ORM model.

Revision ID: 20260722_0006
Revises: 20260722_0005
"""

import sqlalchemy as sa
from alembic import op

revision = "20260722_0006"
down_revision = "20260722_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rendered_answers",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    raise RuntimeError("The breaking garment-intelligence cutover is forward-only.")
