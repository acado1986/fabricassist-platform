"""Add auth rotation and direct-upload lifecycle fields.

Revision ID: 20260721_0002
Revises: 20260721_0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260721_0002"
down_revision = "20260721_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("refresh_sessions", sa.Column("replaced_by_id", postgresql.UUID(as_uuid=True)))
    op.add_column(
        "scan_images", sa.Column("upload_token", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "scan_images", sa.Column("upload_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "scan_images", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.alter_column("scan_images", "mime_type", nullable=True)
    op.alter_column("scan_images", "byte_size", nullable=True)
    op.alter_column("scan_images", "width", nullable=True)
    op.alter_column("scan_images", "height", nullable=True)
    op.alter_column("scan_images", "sha256", nullable=True)
    op.drop_constraint("ck_scan_images_byte_size", "scan_images", type_="check")
    op.drop_constraint("ck_scan_images_width", "scan_images", type_="check")
    op.drop_constraint("ck_scan_images_height", "scan_images", type_="check")
    op.create_check_constraint(
        "ck_scan_images_byte_size", "scan_images", "byte_size > 0 OR byte_size IS NULL"
    )
    op.create_check_constraint("ck_scan_images_width", "scan_images", "width > 0 OR width IS NULL")
    op.create_check_constraint(
        "ck_scan_images_height", "scan_images", "height > 0 OR height IS NULL"
    )
    op.create_unique_constraint("uq_scan_images_upload_token", "scan_images", ["upload_token"])
    op.alter_column("scan_images", "upload_token", nullable=False)
    op.alter_column("scan_images", "upload_expires_at", nullable=False)


def downgrade() -> None:
    op.drop_constraint("uq_scan_images_upload_token", "scan_images", type_="unique")
    op.drop_constraint("ck_scan_images_height", "scan_images", type_="check")
    op.drop_constraint("ck_scan_images_width", "scan_images", type_="check")
    op.drop_constraint("ck_scan_images_byte_size", "scan_images", type_="check")
    op.create_check_constraint("ck_scan_images_byte_size", "scan_images", "byte_size > 0")
    op.create_check_constraint("ck_scan_images_width", "scan_images", "width > 0")
    op.create_check_constraint("ck_scan_images_height", "scan_images", "height > 0")
    op.alter_column("scan_images", "sha256", nullable=False)
    op.alter_column("scan_images", "height", nullable=False)
    op.alter_column("scan_images", "width", nullable=False)
    op.alter_column("scan_images", "byte_size", nullable=False)
    op.alter_column("scan_images", "mime_type", nullable=False)
    op.drop_column("scan_images", "completed_at")
    op.drop_column("scan_images", "upload_expires_at")
    op.drop_column("scan_images", "upload_token")
    op.drop_column("refresh_sessions", "replaced_by_id")
