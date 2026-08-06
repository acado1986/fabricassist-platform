"""Add the self-reference used by hidden merged garment tombstones.

Revision ID: 20260731_0022
Revises: 20260731_0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260731_0022"
down_revision: str | None = "20260731_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The guarded DDL also repairs environments that received the merged
    # garment migration from the earlier release branch before this branch was
    # rebased onto the unified API history.
    op.execute(
        sa.text(
            """
            ALTER TABLE garments
                ADD COLUMN IF NOT EXISTS merged_into_id UUID,
                ADD COLUMN IF NOT EXISTS merged_at TIMESTAMP WITH TIME ZONE
            """
        )
    )
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'fk_garments_merged_into_id'
                ) THEN
                    ALTER TABLE garments
                    ADD CONSTRAINT fk_garments_merged_into_id
                    FOREIGN KEY (merged_into_id) REFERENCES garments(id)
                    ON DELETE RESTRICT;
                END IF;
            END $$;
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_garments_merged_into_id ON garments (merged_into_id)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_garments_merged_into_id"))
    op.execute(sa.text("ALTER TABLE garments DROP CONSTRAINT IF EXISTS fk_garments_merged_into_id"))
    op.execute(sa.text("ALTER TABLE garments DROP COLUMN IF EXISTS merged_at"))
    op.execute(sa.text("ALTER TABLE garments DROP COLUMN IF EXISTS merged_into_id"))
