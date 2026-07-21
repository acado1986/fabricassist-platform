"""Add asynchronous analysis, extraction, and rendered-result storage.

Revision ID: 20260721_0003
Revises: 20260721_0002
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260721_0003"
down_revision = "20260721_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("analysis_operation_key", sa.String(length=255)))
    op.add_column(
        "scans", sa.Column("analysis_attempts", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("scans", sa.Column("analysis_lease_expires_at", sa.DateTime(timezone=True)))
    op.add_column("scans", sa.Column("analysis_error_code", sa.String(length=100)))
    op.add_column("scans", sa.Column("analysis_stage", sa.String(length=100)))
    op.create_unique_constraint(
        "uq_scans_analysis_operation_key", "scans", ["analysis_operation_key"]
    )
    op.create_table(
        "model_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=False),
        sa.Column("schema_version", sa.String(50), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("estimated_cost_usd_micros", sa.Integer()),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("error_code", sa.String(100)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_model_runs_tenant_scan", "model_runs", ["tenant_id", "scan_id"])
    op.create_table(
        "label_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "model_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_runs.id", ondelete="SET NULL"),
        ),
        sa.Column("original_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("validated_data", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("scan_id", name="uq_label_extractions_scan"),
    )
    op.create_index("ix_label_extractions_tenant_id", "label_extractions", ["tenant_id"])
    op.create_table(
        "care_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "extraction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("label_extractions.id", ondelete="SET NULL"),
        ),
        sa.Column("canonical_data", postgresql.JSONB(), nullable=False),
        sa.Column("rules_version", sa.String(50), nullable=False),
        sa.Column("detergent_rules_version", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("scan_id", name="uq_care_results_scan"),
    )
    op.create_index("ix_care_results_tenant_id", "care_results", ["tenant_id"])
    op.create_table(
        "rendered_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "care_result_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("care_results.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("template_version", sa.String(50), nullable=False),
        sa.Column("answer", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "care_result_id",
            "language",
            "template_version",
            name="uq_rendered_answers_result_language_template",
        ),
    )
    op.create_index("ix_rendered_answers_tenant_id", "rendered_answers", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_rendered_answers_tenant_id", table_name="rendered_answers")
    op.drop_table("rendered_answers")
    op.drop_index("ix_care_results_tenant_id", table_name="care_results")
    op.drop_table("care_results")
    op.drop_index("ix_label_extractions_tenant_id", table_name="label_extractions")
    op.drop_table("label_extractions")
    op.drop_index("ix_model_runs_tenant_scan", table_name="model_runs")
    op.drop_table("model_runs")
    op.drop_constraint("uq_scans_analysis_operation_key", "scans", type_="unique")
    op.drop_column("scans", "analysis_stage")
    op.drop_column("scans", "analysis_error_code")
    op.drop_column("scans", "analysis_lease_expires_at")
    op.drop_column("scans", "analysis_attempts")
    op.drop_column("scans", "analysis_operation_key")
