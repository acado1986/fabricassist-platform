"""Allow one durable operation row per QStash analysis stage.

Revision ID: 20260728_0017
Revises: 20260728_0016
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260728_0017"
down_revision: str | None = "20260728_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_analysis_job_operations_scan_key",
        "analysis_job_operations",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_analysis_job_operations_scan_key_stage",
        "analysis_job_operations",
        ["scan_id", "operation_key", "stage"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_analysis_job_operations_scan_key_stage",
        "analysis_job_operations",
        type_="unique",
    )
    op.execute("DELETE FROM analysis_job_operations WHERE stage <> 'validate_uploaded_images'")
    op.create_unique_constraint(
        "uq_analysis_job_operations_scan_key",
        "analysis_job_operations",
        ["scan_id", "operation_key"],
    )
