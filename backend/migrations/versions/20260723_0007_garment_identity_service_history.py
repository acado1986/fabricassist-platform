"""Add durable exact garment identifiers and append-only service history.

Revision ID: 20260723_0007
Revises: 20260722_0006
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260723_0007"
down_revision = "20260722_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "garment_identifiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("garment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identifier_type", sa.String(40), nullable=False),
        sa.Column("normalized_value", sa.String(255), nullable=False),
        sa.Column("verification_status", sa.String(20), nullable=False, server_default="verified"),
        sa.Column("source", sa.String(40), nullable=False, server_default="fabricassist"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("confirmed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "verified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["garment_id"], ["garments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["confirmed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "tenant_id", "identifier_type", "normalized_value", name="uq_garment_identifiers_exact"
        ),
    )
    op.create_index("ix_garment_identifiers_garment_id", "garment_identifiers", ["garment_id"])
    op.create_table(
        "garment_service_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("garment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "kind IN ('planned', 'performed', 'completed')", name="ck_garment_service_events_kind"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["garment_id"], ["garments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_garment_service_events_garment_created",
        "garment_service_events",
        ["garment_id", "created_at"],
    )
    op.create_index("ix_garment_service_events_tenant_id", "garment_service_events", ["tenant_id"])
    op.create_table(
        "garment_identity_match_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("reasons", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_garment_identity_match_runs_scan", "garment_identity_match_runs", ["scan_id"]
    )
    op.create_table(
        "garment_identity_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("garment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("reasons", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["match_run_id"], ["garment_identity_match_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["garment_id"], ["garments.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "match_run_id", "garment_id", name="uq_garment_identity_candidate_match"
        ),
    )
    op.create_index(
        "ix_garment_identity_candidates_garment", "garment_identity_candidates", ["garment_id"]
    )
    op.create_table(
        "garment_identity_confirmations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("garment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("reasons", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["garment_id"], ["garments.id"]),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["garment_identity_candidates.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("scan_id", name="uq_garment_identity_confirmations_scan"),
    )
    op.create_table(
        "garment_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("garment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observation_type", sa.String(40), nullable=False),
        sa.Column("stability", sa.String(20), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("supersedes_observation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["garment_id"], ["garments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["analysis_revision_id"], ["analysis_revisions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_observation_id"], ["garment_observations.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_garment_observations_garment_created",
        "garment_observations",
        ["garment_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("garment_observations")
    op.drop_table("garment_identity_confirmations")
    op.drop_table("garment_identity_candidates")
    op.drop_table("garment_identity_match_runs")
    op.drop_table("garment_service_events")
    op.drop_table("garment_identifiers")
