"""Add auditable soft-delete state for merged temporary garments.

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


def upgrade() -> None:
    op.add_column(
        "garments",
        sa.Column("merged_into_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "garments",
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_garments_merged_into_id",
        "garments",
        "garments",
        ["merged_into_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_garments_merged_into_id", "garments", ["merged_into_id"])


def downgrade() -> None:
    op.drop_index("ix_garments_merged_into_id", table_name="garments")
    op.drop_constraint("fk_garments_merged_into_id", "garments", type_="foreignkey")
    op.drop_column("garments", "merged_at")
    op.drop_column("garments", "merged_into_id")
