"""Create the tenant, identity, scan, and ruleset storage baseline.

Revision ID: 20260721_0001
Revises:
Create Date: 2026-07-21 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260721_0001"
down_revision = None
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()
UTC_TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    """Create only the Phase 5 baseline; no feature-specific tables are included."""
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "tenants",
        sa.Column("id", UUID, nullable=False),
        sa.Column("slug", sa.String(length=63), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("default_language", sa.String(length=2), server_default="en", nullable=False),
        sa.Column("image_retention_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column(
            "created_at", UTC_TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", UTC_TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("char_length(slug) >= 3", name="ck_tenants_slug_length"),
        sa.CheckConstraint("char_length(name) >= 1", name="ck_tenants_name_not_empty"),
        sa.CheckConstraint("default_language IN ('en', 'es')", name="ck_tenants_default_language"),
        sa.CheckConstraint("image_retention_days > 0", name="ck_tenants_image_retention_days"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "users",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), server_default="customer", nullable=False),
        sa.Column("preferred_language", sa.String(length=2), server_default="en", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at", UTC_TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", UTC_TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("role IN ('customer', 'operator', 'admin')", name="ck_users_role"),
        sa.CheckConstraint(
            "preferred_language IN ('en', 'es')", name="ck_users_preferred_language"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_table(
        "refresh_sessions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("family_id", UUID, nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", UTC_TIMESTAMP, nullable=False),
        sa.Column("revoked_at", UTC_TIMESTAMP, nullable=True),
        sa.Column("metadata_json", JSONB, server_default="{}", nullable=False),
        sa.Column(
            "created_at", UTC_TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint(
            "char_length(token_hash) >= 32", name="ck_refresh_sessions_token_hash_length"
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_refresh_sessions_expiry"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_refresh_sessions_tenant_id", "refresh_sessions", ["tenant_id"])
    op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])
    op.create_index("ix_refresh_sessions_family_id", "refresh_sessions", ["family_id"])
    op.create_table(
        "scans",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=True),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("requested_language", sa.String(length=2), server_default="en", nullable=False),
        sa.Column("progress_percent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", UTC_TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", UTC_TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'uploading', 'queued', 'processing', 'needs_better_image', "
            "'needs_review', 'completed', 'failed', 'deleted')",
            name="ck_scans_status",
        ),
        sa.CheckConstraint("progress_percent BETWEEN 0 AND 100", name="ck_scans_progress_percent"),
        sa.CheckConstraint("version >= 1", name="ck_scans_version"),
        sa.CheckConstraint(
            "requested_language IN ('en', 'es')", name="ck_scans_requested_language"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scans_tenant_id", "scans", ["tenant_id"])
    op.create_index("ix_scans_tenant_created_at", "scans", ["tenant_id", "created_at"])
    op.create_index("ix_scans_user_id", "scans", ["user_id"])
    op.create_table(
        "scan_images",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("scan_id", UUID, nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", UTC_TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('garment', 'care_label', 'other')", name="ck_scan_images_kind"
        ),
        sa.CheckConstraint("byte_size > 0", name="ck_scan_images_byte_size"),
        sa.CheckConstraint("width > 0", name="ck_scan_images_width"),
        sa.CheckConstraint("height > 0", name="ck_scan_images_height"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_id", "object_key", name="uq_scan_images_scan_object_key"),
    )
    op.create_index("ix_scan_images_tenant_id", "scan_images", ["tenant_id"])
    op.create_index("ix_scan_images_scan_id", "scan_images", ["scan_id"])
    op.create_table(
        "idempotency_records",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=True),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", JSONB, nullable=True),
        sa.Column("expires_at", UTC_TIMESTAMP, nullable=False),
        sa.Column(
            "created_at", UTC_TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("char_length(idempotency_key) >= 1", name="ck_idempotency_records_key"),
        sa.CheckConstraint("char_length(operation) >= 1", name="ck_idempotency_records_operation"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "operation",
            "idempotency_key",
            name="uq_idempotency_records_tenant_operation_key",
        ),
    )
    op.create_index("ix_idempotency_records_tenant_id", "idempotency_records", ["tenant_id"])
    op.create_table(
        "ruleset_versions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("ruleset_type", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", UTC_TIMESTAMP, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint(
            "ruleset_type IN ('care', 'detergent', 'rendering')", name="ck_ruleset_versions_type"
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'retired')", name="ck_ruleset_versions_status"
        ),
        sa.CheckConstraint("version >= 1", name="ck_ruleset_versions_version"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "ruleset_type", "version", name="uq_ruleset_versions_tenant_type_version"
        ),
    )
    op.create_index("ix_ruleset_versions_tenant_id", "ruleset_versions", ["tenant_id"])


def downgrade() -> None:
    """Remove this initial baseline only; intended for empty/test databases."""
    op.drop_table("ruleset_versions")
    op.drop_table("idempotency_records")
    op.drop_table("scan_images")
    op.drop_table("scans")
    op.drop_table("refresh_sessions")
    op.drop_table("users")
    op.drop_table("tenants")
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS citext")
