"""Hide legacy garment rows that no longer have a live scan reference.

Revision ID: 20260731_0021
Revises: 20260731_0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260731_0021"
down_revision: str | None = "20260731_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A garment is user-visible only while at least one non-deleted scan still
    # points to it. Existing rows are repaired here; future reassignment uses
    # archive_if_orphaned in the identity-confirmation flow.
    op.execute(
        sa.text(
            """
            UPDATE garments AS garment
            SET archived_at = CURRENT_TIMESTAMP
            WHERE garment.archived_at IS NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM scans
                  WHERE scans.garment_id = garment.id
                    AND scans.status <> 'deleted'
              )
            """
        )
    )


def downgrade() -> None:
    # Cannot safely distinguish rows archived by this repair from a prior user
    # archive, so the data repair is intentionally not reversed. The no-op
    # downgrade still lets Alembic traverse older schema revisions safely.
    pass
