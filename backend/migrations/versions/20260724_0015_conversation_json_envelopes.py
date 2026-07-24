"""Use object envelopes for conversation JSON defaults.

Revision ID: 20260724_0015
Revises: 20260723_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260724_0015"
down_revision: str | None = "20260723_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    "actionable_claims",
    "evidence_ids",
    "uncertainties",
    "follow_up_questions",
)


def upgrade() -> None:
    for column in _COLUMNS:
        op.alter_column(
            "conversation_messages",
            column,
            existing_type=postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
        )


def downgrade() -> None:
    for column in _COLUMNS:
        op.alter_column(
            "conversation_messages",
            column,
            existing_type=postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
        )
