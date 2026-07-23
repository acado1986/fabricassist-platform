"""Add provider usage and failure observability to model runs.

Revision ID: 20260723_0014
Revises: 20260723_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0014"
down_revision: str | None = "20260723_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("model_runs", sa.Column("estimated_cost_usd", sa.Numeric(12, 6), nullable=True))
    op.alter_column("model_runs", "error_code", new_column_name="error_category")
    op.execute(
        """
        UPDATE model_runs
        SET estimated_cost_usd = estimated_cost_usd_micros::numeric / 1000000
        WHERE estimated_cost_usd_micros IS NOT NULL
        """
    )
    op.drop_column("model_runs", "estimated_cost_usd_micros")
    op.create_check_constraint(
        "ck_model_runs_latency_nonnegative",
        "model_runs",
        "latency_ms IS NULL OR latency_ms >= 0",
    )
    op.create_check_constraint(
        "ck_model_runs_input_tokens_nonnegative",
        "model_runs",
        "input_tokens IS NULL OR input_tokens >= 0",
    )
    op.create_check_constraint(
        "ck_model_runs_output_tokens_nonnegative",
        "model_runs",
        "output_tokens IS NULL OR output_tokens >= 0",
    )
    op.create_check_constraint(
        "ck_model_runs_cost_nonnegative",
        "model_runs",
        "estimated_cost_usd IS NULL OR estimated_cost_usd >= 0",
    )


def downgrade() -> None:
    op.alter_column("model_runs", "error_category", new_column_name="error_code")
    op.add_column("model_runs", sa.Column("estimated_cost_usd_micros", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE model_runs
        SET estimated_cost_usd_micros = round(estimated_cost_usd * 1000000)::integer
        WHERE estimated_cost_usd IS NOT NULL
        """
    )
    op.drop_constraint("ck_model_runs_cost_nonnegative", "model_runs", type_="check")
    op.drop_constraint("ck_model_runs_output_tokens_nonnegative", "model_runs", type_="check")
    op.drop_constraint("ck_model_runs_input_tokens_nonnegative", "model_runs", type_="check")
    op.drop_constraint("ck_model_runs_latency_nonnegative", "model_runs", type_="check")
    op.drop_column("model_runs", "estimated_cost_usd")
