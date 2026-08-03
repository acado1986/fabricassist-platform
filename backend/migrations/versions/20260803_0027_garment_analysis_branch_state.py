"""Pin garment-analysis behavior and persist durable branch execution state.

Revision ID: 20260803_0027
Revises: 20260803_0026
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260803_0027"
down_revision = "20260803_0026"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column(
        "analysis_revisions",
        sa.Column(
            "module_version",
            sa.String(length=100),
            nullable=False,
            server_default="garment-analysis-v1",
        ),
    )
    op.add_column(
        "analysis_revisions",
        sa.Column(
            "workflow_version",
            sa.String(length=100),
            nullable=False,
            server_default="garment-analysis-v1",
        ),
    )
    for column in (
        "merged_schema_version",
        "care_policy_version",
        "confidence_policy_version",
        "retry_policy_version",
    ):
        op.add_column(
            "analysis_revisions",
            sa.Column(column, sa.String(length=100), nullable=False, server_default="unknown"),
        )
    op.add_column(
        "analysis_revisions",
        sa.Column(
            "effective_feature_flags",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("analysis_revisions", sa.Column("finalized_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "ck_analysis_revisions_module_version",
        "analysis_revisions",
        "char_length(module_version) >= 1",
    )
    op.create_check_constraint(
        "ck_analysis_revisions_workflow_version",
        "analysis_revisions",
        "char_length(workflow_version) >= 1",
    )
    op.create_index(
        "ix_analysis_revisions_tenant_workflow",
        "analysis_revisions",
        ["tenant_id", "workflow_version"],
    )

    op.create_table(
        "behavior_versions",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("behavior_type", sa.String(length=40), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "behavior_type IN ('module', 'workflow', 'prompt', 'schema', 'preprocessing', "
            "'confidence_policy', 'retry_policy', 'stain_policy', 'feature_flags')",
            name="ck_behavior_versions_type",
        ),
        sa.CheckConstraint("status IN ('active', 'retired')", name="ck_behavior_versions_status"),
        sa.UniqueConstraint(
            "tenant_id", "behavior_type", "version", name="uq_behavior_versions_tenant_type_version"
        ),
    )
    op.create_index(
        "ix_behavior_versions_tenant_type", "behavior_versions", ["tenant_id", "behavior_type"]
    )

    op.create_table(
        "analysis_branch_results",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "analysis_revision_id",
            UUID,
            sa.ForeignKey("analysis_revisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("branch_name", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claim_token", UUID),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("provider", sa.String(length=100)),
        sa.Column("model", sa.String(length=200)),
        sa.Column("prompt_version", sa.String(length=100)),
        sa.Column("schema_version", sa.String(length=100)),
        sa.Column("preprocessing_version", sa.String(length=100)),
        sa.Column("request_fingerprint", sa.String(length=64)),
        sa.Column("overall_confidence", sa.Integer()),
        sa.Column("uncertain_fields", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("result_payload", JSONB),
        sa.Column("error_category", sa.String(length=100)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "branch_name IN ('garment_inspection', 'label_extraction', 'stain_treatment')",
            name="ck_analysis_branch_results_name",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'retryable_failed', "
            "'permanent_failed', 'needs_input', 'not_provided')",
            name="ck_analysis_branch_results_status",
        ),
        sa.CheckConstraint(
            "attempt_count BETWEEN 0 AND 2", name="ck_analysis_branch_results_attempt_count"
        ),
        sa.CheckConstraint(
            "overall_confidence BETWEEN 0 AND 100 OR overall_confidence IS NULL",
            name="ck_analysis_branch_results_confidence",
        ),
        sa.CheckConstraint(
            "(status = 'running' AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (status <> 'running' AND claim_token IS NULL)",
            name="ck_analysis_branch_results_lease_state",
        ),
        sa.CheckConstraint(
            "status <> 'completed' OR result_payload IS NOT NULL",
            name="ck_analysis_branch_results_completed_payload",
        ),
        sa.UniqueConstraint(
            "analysis_revision_id", "branch_name", name="uq_analysis_branch_revision_name"
        ),
    )
    op.create_index(
        "ix_analysis_branch_results_tenant_status",
        "analysis_branch_results",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_analysis_branch_results_revision_status",
        "analysis_branch_results",
        ["analysis_revision_id", "status"],
    )
    op.create_index(
        "ix_analysis_branch_results_lease",
        "analysis_branch_results",
        ["status", "lease_expires_at"],
    )

    op.add_column(
        "model_runs",
        sa.Column(
            "analysis_revision_id",
            UUID,
            sa.ForeignKey("analysis_revisions.id", ondelete="CASCADE"),
        ),
    )
    op.add_column(
        "model_runs",
        sa.Column(
            "analysis_branch_result_id",
            UUID,
            sa.ForeignKey("analysis_branch_results.id", ondelete="CASCADE"),
        ),
    )
    op.add_column("model_runs", sa.Column("retry_number", sa.Integer()))
    op.add_column("model_runs", sa.Column("image_count", sa.Integer()))
    op.add_column("model_runs", sa.Column("role_counts", JSONB))
    for column in ("total_tokens", "cached_tokens", "thought_tokens", "tool_tokens"):
        op.add_column("model_runs", sa.Column(column, sa.Integer()))
    op.add_column("model_runs", sa.Column("response_model_version", sa.String(length=100)))
    op.add_column("model_runs", sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.create_index(
        "ix_model_runs_revision_branch",
        "model_runs",
        ["analysis_revision_id", "analysis_branch_result_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_model_runs_revision_branch", table_name="model_runs")
    for column in (
        "completed_at",
        "response_model_version",
        "tool_tokens",
        "thought_tokens",
        "cached_tokens",
        "total_tokens",
        "role_counts",
        "image_count",
        "retry_number",
        "analysis_branch_result_id",
        "analysis_revision_id",
    ):
        op.drop_column("model_runs", column)

    op.drop_index("ix_analysis_branch_results_lease", table_name="analysis_branch_results")
    op.drop_index(
        "ix_analysis_branch_results_revision_status", table_name="analysis_branch_results"
    )
    op.drop_index("ix_analysis_branch_results_tenant_status", table_name="analysis_branch_results")
    op.drop_table("analysis_branch_results")
    op.drop_index("ix_behavior_versions_tenant_type", table_name="behavior_versions")
    op.drop_table("behavior_versions")

    op.drop_index("ix_analysis_revisions_tenant_workflow", table_name="analysis_revisions")
    op.drop_constraint(
        "ck_analysis_revisions_workflow_version", "analysis_revisions", type_="check"
    )
    op.drop_constraint("ck_analysis_revisions_module_version", "analysis_revisions", type_="check")
    for column in (
        "finalized_at",
        "effective_feature_flags",
        "retry_policy_version",
        "confidence_policy_version",
        "care_policy_version",
        "merged_schema_version",
        "workflow_version",
        "module_version",
    ):
        op.drop_column("analysis_revisions", column)
