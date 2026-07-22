"""Persist constrained care-planning retry counts.

Revision ID: 20260722_0005
Revises: 20260722_0004
"""

import sqlalchemy as sa
from alembic import op

revision = "20260722_0005"
down_revision = "20260722_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proposed_care_plans",
        sa.Column("retry_number", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_proposed_care_plans_retry_number", "proposed_care_plans", "retry_number BETWEEN 0 AND 1"
    )


def downgrade() -> None:
    raise RuntimeError("The breaking garment-intelligence cutover is forward-only.")
