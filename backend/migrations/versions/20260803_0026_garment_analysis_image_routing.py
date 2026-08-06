"""Persist explicit image routing metadata and local quality signals.

Revision ID: 20260803_0026
Revises: 20260731_0022
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260803_0026"
down_revision = "20260731_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scan_images", sa.Column("viewpoint", sa.String(16)))
    op.add_column("scan_images", sa.Column("label_scope", sa.String(16)))
    op.add_column("scan_images", sa.Column("quality_state", sa.String(16)))
    op.add_column("scan_images", sa.Column("blur_score", sa.Float))
    op.add_column("scan_images", sa.Column("brightness_score", sa.Float))
    op.add_column("scan_images", sa.Column("contrast_score", sa.Float))
    op.add_column("scan_images", sa.Column("glare_score", sa.Float))
    op.add_column("scan_images", sa.Column("crop_readability_score", sa.Float))
    op.add_column("scan_images", sa.Column("orientation_degrees", sa.Integer))
    op.add_column("scan_images", sa.Column("quality_checked_at", sa.DateTime(timezone=True)))
    op.add_column("scan_images", sa.Column("preprocessing_version", sa.String(50)))
    op.add_column("scan_images", sa.Column("normalized_object_key", sa.Text))
    op.create_check_constraint(
        "ck_scan_images_viewpoint",
        "scan_images",
        "viewpoint IN ('front','back','side','detail','unknown') OR viewpoint IS NULL",
    )
    op.create_check_constraint(
        "ck_scan_images_viewpoint_role",
        "scan_images",
        "viewpoint IS NULL OR viewpoint = 'unknown' OR role IN "
        "('garment_overview','construction_detail')",
    )
    op.create_check_constraint(
        "ck_scan_images_label_scope",
        "scan_images",
        "label_scope IN ('care','composition','combined','unknown') OR label_scope IS NULL",
    )
    op.create_check_constraint(
        "ck_scan_images_label_scope_role",
        "scan_images",
        "label_scope IS NULL OR label_scope = 'unknown' OR role IN "
        "('care_label','composition_label')",
    )
    op.create_check_constraint(
        "ck_scan_images_quality_state",
        "scan_images",
        "quality_state IN ('usable','borderline','unusable','unknown') OR quality_state IS NULL",
    )
    op.create_check_constraint(
        "ck_scan_images_quality_scores",
        "scan_images",
        "(blur_score BETWEEN 0 AND 1 OR blur_score IS NULL) AND "
        "(brightness_score BETWEEN 0 AND 1 OR brightness_score IS NULL) AND "
        "(contrast_score BETWEEN 0 AND 1 OR contrast_score IS NULL) AND "
        "(glare_score BETWEEN 0 AND 1 OR glare_score IS NULL) AND "
        "(crop_readability_score BETWEEN 0 AND 1 OR crop_readability_score IS NULL)",
    )
    op.create_check_constraint(
        "ck_scan_images_orientation_degrees",
        "scan_images",
        "orientation_degrees IN (0,90,180,270) OR orientation_degrees IS NULL",
    )
    op.create_index(
        "ix_scan_images_tenant_quality_state",
        "scan_images",
        ["tenant_id", "quality_state"],
    )


def downgrade() -> None:
    op.drop_index("ix_scan_images_tenant_quality_state", table_name="scan_images")
    for constraint in (
        "ck_scan_images_orientation_degrees",
        "ck_scan_images_quality_scores",
        "ck_scan_images_quality_state",
        "ck_scan_images_label_scope_role",
        "ck_scan_images_label_scope",
        "ck_scan_images_viewpoint_role",
        "ck_scan_images_viewpoint",
    ):
        op.drop_constraint(constraint, "scan_images", type_="check")
    for column in (
        "normalized_object_key",
        "preprocessing_version",
        "quality_checked_at",
        "orientation_degrees",
        "crop_readability_score",
        "glare_score",
        "contrast_score",
        "brightness_score",
        "blur_score",
        "quality_state",
        "label_scope",
        "viewpoint",
    ):
        op.drop_column("scan_images", column)
