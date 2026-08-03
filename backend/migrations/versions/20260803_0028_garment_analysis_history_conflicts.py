"""Add append-only garment-analysis history, correction, and conflict details.

Revision ID: 20260803_0028
Revises: 20260803_0027
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260803_0028"
down_revision = "20260803_0027"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column(
        "garment_service_events",
        sa.Column("method", sa.String(80), nullable=False, server_default="unknown"),
    )
    op.add_column("garment_service_events", sa.Column("water_temperature_c", sa.Integer()))
    op.add_column("garment_service_events", sa.Column("cycle", sa.String(80)))
    op.add_column("garment_service_events", sa.Column("detergent_category", sa.String(120)))
    op.add_column("garment_service_events", sa.Column("detergent_text", sa.String(500)))
    op.add_column(
        "garment_service_events",
        sa.Column("stain_products", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column("garment_service_events", sa.Column("drying_method", sa.String(80)))
    op.add_column("garment_service_events", sa.Column("ironing_method", sa.String(80)))
    op.add_column(
        "garment_service_events",
        sa.Column("outcome", sa.String(20), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "garment_service_events",
        sa.Column("observed_effects", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "garment_service_events",
        sa.Column("confirmed_by", sa.String(80), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "garment_service_events",
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.execute("UPDATE garment_service_events SET occurred_at = created_at")
    op.add_column(
        "garment_service_events",
        sa.Column(
            "detail_schema_version",
            sa.String(80),
            nullable=False,
            server_default="service-event-v1",
        ),
    )
    op.add_column(
        "garment_service_events",
        sa.Column("detail_snapshot", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "garment_service_events",
        sa.Column(
            "exact_garment_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "garment_service_events",
        sa.Column("invalidated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "garment_service_events",
        sa.Column(
            "superseded_by_event_id",
            UUID,
            sa.ForeignKey("garment_service_events.id", ondelete="SET NULL"),
        ),
    )
    op.create_check_constraint(
        "ck_garment_service_events_outcome",
        "garment_service_events",
        "outcome IN ('successful', 'damaging', 'unknown')",
    )
    op.create_check_constraint(
        "ck_garment_service_events_water_temperature",
        "garment_service_events",
        "water_temperature_c BETWEEN 10 AND 95 OR water_temperature_c IS NULL",
    )
    op.create_index(
        "ix_garment_service_events_tenant_garment_outcome",
        "garment_service_events",
        ["tenant_id", "garment_id", "outcome", "occurred_at"],
    )

    op.alter_column("evidence_corrections", "review_case_id", nullable=True)
    op.add_column(
        "evidence_corrections",
        sa.Column("field_path", sa.String(160), nullable=False, server_default="unknown"),
    )
    op.add_column("evidence_corrections", sa.Column("previous_value", JSONB))
    op.add_column("evidence_corrections", sa.Column("corrected_value", JSONB))
    op.add_column(
        "evidence_corrections",
        sa.Column("source_image_id", UUID, sa.ForeignKey("scan_images.id", ondelete="SET NULL")),
    )
    op.add_column(
        "evidence_corrections",
        sa.Column("source", sa.String(20), nullable=False, server_default="operator"),
    )
    op.add_column(
        "evidence_corrections",
        sa.Column("confirmation", sa.String(20), nullable=False, server_default="accepted"),
    )
    op.add_column(
        "evidence_corrections",
        sa.Column(
            "supersedes_correction_id",
            UUID,
            sa.ForeignKey("evidence_corrections.id", ondelete="SET NULL"),
        ),
    )
    op.create_check_constraint(
        "ck_evidence_corrections_source",
        "evidence_corrections",
        "source IN ('customer', 'operator', 'system')",
    )
    op.create_check_constraint(
        "ck_evidence_corrections_confirmation",
        "evidence_corrections",
        "confirmation IN ('pending_review', 'accepted', 'rejected')",
    )
    op.create_index(
        "ix_evidence_corrections_tenant_original_field",
        "evidence_corrections",
        ["tenant_id", "original_revision_id", "field_path"],
    )

    op.create_table(
        "evidence_conflicts",
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
        sa.Column("field_path", sa.String(160), nullable=False),
        sa.Column("values", JSONB, nullable=False),
        sa.Column("evidence", JSONB, nullable=False),
        sa.Column("selected_value", JSONB),
        sa.Column("resolution_code", sa.String(120), nullable=False),
        sa.Column("explanation_key", sa.String(120), nullable=False),
        sa.Column("safety_critical", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("char_length(field_path) >= 1", name="ck_evidence_conflicts_field_path"),
        sa.UniqueConstraint(
            "analysis_revision_id",
            "field_path",
            "resolution_code",
            name="uq_evidence_conflicts_revision_field_resolution",
        ),
    )
    op.create_index(
        "ix_evidence_conflicts_tenant_revision",
        "evidence_conflicts",
        ["tenant_id", "analysis_revision_id"],
    )
    op.create_index(
        "ix_evidence_conflicts_tenant_safety",
        "evidence_conflicts",
        ["tenant_id", "safety_critical"],
    )


def downgrade() -> None:
    op.drop_index("ix_evidence_conflicts_tenant_safety", table_name="evidence_conflicts")
    op.drop_index("ix_evidence_conflicts_tenant_revision", table_name="evidence_conflicts")
    op.drop_table("evidence_conflicts")
    op.drop_index(
        "ix_evidence_corrections_tenant_original_field", table_name="evidence_corrections"
    )
    op.drop_constraint(
        "ck_evidence_corrections_confirmation", "evidence_corrections", type_="check"
    )
    op.drop_constraint("ck_evidence_corrections_source", "evidence_corrections", type_="check")
    for column in (
        "supersedes_correction_id",
        "confirmation",
        "source",
        "source_image_id",
        "corrected_value",
        "previous_value",
        "field_path",
    ):
        op.drop_column("evidence_corrections", column)
    op.alter_column("evidence_corrections", "review_case_id", nullable=False)
    op.drop_index(
        "ix_garment_service_events_tenant_garment_outcome", table_name="garment_service_events"
    )
    op.drop_constraint(
        "ck_garment_service_events_water_temperature", "garment_service_events", type_="check"
    )
    op.drop_constraint("ck_garment_service_events_outcome", "garment_service_events", type_="check")
    for column in (
        "superseded_by_event_id",
        "invalidated",
        "exact_garment_confirmed",
        "detail_snapshot",
        "detail_schema_version",
        "occurred_at",
        "confirmed_by",
        "observed_effects",
        "outcome",
        "ironing_method",
        "drying_method",
        "stain_products",
        "detergent_text",
        "detergent_category",
        "cycle",
        "water_temperature_c",
        "method",
    ):
        op.drop_column("garment_service_events", column)
