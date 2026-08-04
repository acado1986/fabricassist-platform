"""Baseline persistence schema; it deliberately contains no authentication behavior."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Declarative metadata used by Alembic's initial baseline migration."""


Uuid = PostgreSQLUUID(as_uuid=True)
UtcTimestamp = DateTime(timezone=True)


class Tenant(Base):
    """A tenant boundary record; tenant authorization is introduced in Phase 6."""

    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("char_length(slug) >= 3", name="ck_tenants_slug_length"),
        CheckConstraint("char_length(name) >= 1", name="ck_tenants_name_not_empty"),
        CheckConstraint("default_language IN ('en', 'es')", name="ck_tenants_default_language"),
        CheckConstraint("image_retention_days > 0", name="ck_tenants_image_retention_days"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    default_language: Mapped[str] = mapped_column(String(2), nullable=False, server_default="en")
    image_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30")
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class User(Base):
    """A user identity record; credentials and authentication flows are deferred."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('customer', 'operator', 'admin')", name="ck_users_role"),
        CheckConstraint("preferred_language IN ('en', 'es')", name="ck_users_preferred_language"),
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        Index("ix_users_tenant_id", "tenant_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="customer")
    preferred_language: Mapped[str] = mapped_column(String(2), nullable=False, server_default="en")
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RefreshSession(Base):
    """Hashed refresh-session storage; Phase 6 owns issuance and rotation."""

    __tablename__ = "refresh_sessions"
    __table_args__ = (
        CheckConstraint(
            "char_length(token_hash) >= 32", name="ck_refresh_sessions_token_hash_length"
        ),
        CheckConstraint("expires_at > created_at", name="ck_refresh_sessions_expiry"),
        Index("ix_refresh_sessions_tenant_id", "tenant_id"),
        Index("ix_refresh_sessions_user_id", "user_id"),
        Index("ix_refresh_sessions_family_id", "family_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    family_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(UtcTimestamp, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    replaced_by_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class Scan(Base):
    """Scan lifecycle storage only; no upload or analysis behavior exists in this phase."""

    __tablename__ = "scans"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'uploading', 'queued', 'processing', 'needs_better_image', "
            "'needs_review', 'completed', 'failed', 'deleted')",
            name="ck_scans_status",
        ),
        CheckConstraint("progress_percent BETWEEN 0 AND 100", name="ck_scans_progress_percent"),
        CheckConstraint("version >= 1", name="ck_scans_version"),
        CheckConstraint("requested_language IN ('en', 'es')", name="ck_scans_requested_language"),
        Index("ix_scans_tenant_id", "tenant_id"),
        Index("ix_scans_tenant_created_at", "tenant_id", "created_at"),
        Index("ix_scans_user_id", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft")
    requested_language: Mapped[str] = mapped_column(String(2), nullable=False, server_default="en")
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    analysis_operation_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    analysis_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    analysis_lease_expires_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    analysis_error_code: Mapped[str | None] = mapped_column(String(100))
    analysis_stage: Mapped[str | None] = mapped_column(String(100))
    garment_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    active_analysis_revision_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    active_result_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AnalysisJobOperation(Base):
    """PostgreSQL-authoritative analysis intent/outbox and stage checkpoint."""

    __tablename__ = "analysis_job_operations"
    __table_args__ = (
        UniqueConstraint(
            "scan_id",
            "operation_key",
            "stage",
            name="uq_analysis_job_operations_scan_key_stage",
        ),
        Index("ix_analysis_job_operations_scan_id", "scan_id"),
        Index(
            "ix_analysis_job_operations_unpublished",
            "status",
            "published_at",
            "created_at",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    scan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    revision_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    operation_key: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    correlation_id: Mapped[str] = mapped_column(
        String(36), nullable=False, default="00000000-0000-0000-0000-000000000000"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="queued")
    lease_expires_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    published_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    completed_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    run_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("ai_runs.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class ScanImage(Base):
    """Private object metadata only; object bytes remain in S3-compatible storage."""

    __tablename__ = "scan_images"
    __table_args__ = (
        CheckConstraint(
            (
                "role IN ('garment_overview','care_label','composition_label',"
                "'barcode_brand_label','stain_closeup','damage_closeup',"
                "'construction_detail','other')"
            ),
            name="ck_scan_images_role",
        ),
        CheckConstraint(
            "viewpoint IN ('front','back','side','detail','unknown') OR viewpoint IS NULL",
            name="ck_scan_images_viewpoint",
        ),
        CheckConstraint(
            "viewpoint IS NULL OR viewpoint = 'unknown' OR role IN "
            "('garment_overview','construction_detail')",
            name="ck_scan_images_viewpoint_role",
        ),
        CheckConstraint(
            "label_scope IN ('care','composition','combined','unknown') OR label_scope IS NULL",
            name="ck_scan_images_label_scope",
        ),
        CheckConstraint(
            "label_scope IS NULL OR label_scope = 'unknown' OR role IN "
            "('care_label','composition_label')",
            name="ck_scan_images_label_scope_role",
        ),
        CheckConstraint(
            "quality_state IN ('usable','borderline','unusable','unknown') "
            "OR quality_state IS NULL",
            name="ck_scan_images_quality_state",
        ),
        CheckConstraint(
            "(blur_score BETWEEN 0 AND 1 OR blur_score IS NULL) AND "
            "(brightness_score BETWEEN 0 AND 1 OR brightness_score IS NULL) AND "
            "(contrast_score BETWEEN 0 AND 1 OR contrast_score IS NULL) AND "
            "(glare_score BETWEEN 0 AND 1 OR glare_score IS NULL) AND "
            "(crop_readability_score BETWEEN 0 AND 1 OR crop_readability_score IS NULL)",
            name="ck_scan_images_quality_scores",
        ),
        CheckConstraint(
            "orientation_degrees IN (0,90,180,270) OR orientation_degrees IS NULL",
            name="ck_scan_images_orientation_degrees",
        ),
        CheckConstraint("byte_size > 0 OR byte_size IS NULL", name="ck_scan_images_byte_size"),
        CheckConstraint("width > 0 OR width IS NULL", name="ck_scan_images_width"),
        CheckConstraint("height > 0 OR height IS NULL", name="ck_scan_images_height"),
        UniqueConstraint("scan_id", "object_key", name="uq_scan_images_scan_object_key"),
        Index("ix_scan_images_tenant_id", "tenant_id"),
        Index("ix_scan_images_scan_id", "scan_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    scan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    detected_role: Mapped[str | None] = mapped_column(String(32))
    viewpoint: Mapped[str | None] = mapped_column(String(16))
    label_scope: Mapped[str | None] = mapped_column(String(16))
    quality_state: Mapped[str | None] = mapped_column(String(16))
    blur_score: Mapped[float | None] = mapped_column(Float)
    brightness_score: Mapped[float | None] = mapped_column(Float)
    contrast_score: Mapped[float | None] = mapped_column(Float)
    glare_score: Mapped[float | None] = mapped_column(Float)
    crop_readability_score: Mapped[float | None] = mapped_column(Float)
    orientation_degrees: Mapped[int | None] = mapped_column(Integer)
    quality_checked_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    preprocessing_version: Mapped[str | None] = mapped_column(String(50))
    normalized_object_key: Mapped[str | None] = mapped_column(Text)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    upload_token: Mapped[UUID] = mapped_column(Uuid, nullable=False, unique=True, default=uuid4)
    upload_expires_at: Mapped[datetime] = mapped_column(UtcTimestamp, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    byte_size: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    normalized_sha256: Mapped[str | None] = mapped_column(String(64))
    perceptual_hash: Mapped[str | None] = mapped_column(String(16))
    deletion_requested_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    deleted_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class IdempotencyRecord(Base):
    """Tenant-scoped idempotency metadata; request handling is deferred."""

    __tablename__ = "idempotency_records"
    __table_args__ = (
        CheckConstraint("char_length(idempotency_key) >= 1", name="ck_idempotency_records_key"),
        CheckConstraint("char_length(operation) >= 1", name="ck_idempotency_records_operation"),
        UniqueConstraint(
            "tenant_id",
            "operation",
            "idempotency_key",
            name="uq_idempotency_records_tenant_operation_key",
        ),
        Index("ix_idempotency_records_tenant_id", "tenant_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(UtcTimestamp, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class RulesetVersion(Base):
    """Immutable version metadata for later deterministic ruleset activation."""

    __tablename__ = "ruleset_versions"
    __table_args__ = (
        CheckConstraint(
            "ruleset_type IN ('care', 'detergent', 'rendering')", name="ck_ruleset_versions_type"
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'retired')", name="ck_ruleset_versions_status"
        ),
        CheckConstraint("version >= 1", name="ck_ruleset_versions_version"),
        UniqueConstraint(
            "tenant_id", "ruleset_type", "version", name="uq_ruleset_versions_tenant_type_version"
        ),
        Index("ix_ruleset_versions_tenant_id", "tenant_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    ruleset_type: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class Garment(Base):
    __tablename__ = "garments"
    __table_args__ = (Index("ix_garments_tenant_id", "tenant_id"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    active_analysis_revision_id: Mapped[UUID | None] = mapped_column(Uuid)
    active_result_id: Mapped[UUID | None] = mapped_column(Uuid)
    display_name: Mapped[str | None] = mapped_column(String(200))
    archived_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class AnalysisRevision(Base):
    __tablename__ = "analysis_revisions"
    __table_args__ = (
        UniqueConstraint("scan_id", "revision_number", name="uq_analysis_revisions_scan_number"),
        CheckConstraint(
            "char_length(module_version) >= 1", name="ck_analysis_revisions_module_version"
        ),
        CheckConstraint(
            "char_length(workflow_version) >= 1", name="ck_analysis_revisions_workflow_version"
        ),
        Index("ix_analysis_revisions_tenant_id", "tenant_id"),
        Index("ix_analysis_revisions_tenant_workflow", "tenant_id", "workflow_version"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    scan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    garment_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("garments.id", ondelete="SET NULL")
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("analysis_revisions.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="processing")
    # Values are pinned at revision creation so redelivery cannot adopt changed settings.
    module_version: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="garment-analysis-v1"
    )
    workflow_version: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="garment-analysis-v1"
    )
    merged_schema_version: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="unknown"
    )
    care_policy_version: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="unknown"
    )
    confidence_policy_version: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="unknown"
    )
    retry_policy_version: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="unknown"
    )
    effective_feature_flags: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    execution_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    finalized_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class RevisionImage(Base):
    __tablename__ = "analysis_revision_images"
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    revision_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analysis_revisions.id", ondelete="CASCADE"), primary_key=True
    )
    image_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("scan_images.id", ondelete="CASCADE"), primary_key=True
    )


class AnalysisBranchResult(Base):
    """The sole durable state for a garment-analysis provider branch.

    The lease token prevents a stale worker from completing work reclaimed by a
    later delivery. Result payloads are validated JSON, never provider SDK objects.
    """

    __tablename__ = "analysis_branch_results"
    __table_args__ = (
        UniqueConstraint(
            "analysis_revision_id", "branch_name", name="uq_analysis_branch_revision_name"
        ),
        CheckConstraint(
            "branch_name IN ('garment_inspection', 'label_extraction', 'stain_treatment', "
            "'barcode_enrichment')",
            name="ck_analysis_branch_results_name",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'retryable_failed', "
            "'permanent_failed', 'needs_input', 'not_provided')",
            name="ck_analysis_branch_results_status",
        ),
        CheckConstraint(
            "attempt_count BETWEEN 0 AND 2", name="ck_analysis_branch_results_attempt_count"
        ),
        CheckConstraint(
            "overall_confidence BETWEEN 0 AND 100 OR overall_confidence IS NULL",
            name="ck_analysis_branch_results_confidence",
        ),
        CheckConstraint(
            "(status = 'running' AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (status <> 'running' AND claim_token IS NULL)",
            name="ck_analysis_branch_results_lease_state",
        ),
        CheckConstraint(
            "status <> 'completed' OR result_payload IS NOT NULL",
            name="ck_analysis_branch_results_completed_payload",
        ),
        Index("ix_analysis_branch_results_tenant_status", "tenant_id", "status"),
        Index("ix_analysis_branch_results_revision_status", "analysis_revision_id", "status"),
        Index("ix_analysis_branch_results_lease", "status", "lease_expires_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    analysis_revision_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analysis_revisions.id", ondelete="CASCADE"), nullable=False
    )
    branch_name: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    claim_token: Mapped[UUID | None] = mapped_column(Uuid)
    lease_expires_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    provider: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(200))
    prompt_version: Mapped[str | None] = mapped_column(String(100))
    schema_version: Mapped[str | None] = mapped_column(String(100))
    preprocessing_version: Mapped[str | None] = mapped_column(String(100))
    request_fingerprint: Mapped[str | None] = mapped_column(String(64))
    overall_confidence: Mapped[int | None] = mapped_column(Integer)
    uncertain_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    cache_provenance: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_category: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    completed_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class BehaviorVersion(Base):
    """Immutable registry for workflow behavior assets outside ruleset_versions."""

    __tablename__ = "behavior_versions"
    __table_args__ = (
        CheckConstraint(
            "behavior_type IN ('module', 'workflow', 'prompt', 'schema', 'preprocessing', "
            "'confidence_policy', 'retry_policy', 'stain_policy', 'feature_flags')",
            name="ck_behavior_versions_type",
        ),
        CheckConstraint("status IN ('active', 'retired')", name="ck_behavior_versions_status"),
        UniqueConstraint(
            "tenant_id", "behavior_type", "version", name="uq_behavior_versions_tenant_type_version"
        ),
        Index("ix_behavior_versions_tenant_type", "tenant_id", "behavior_type"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    behavior_type: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class ModelRun(Base):
    __tablename__ = "model_runs"
    __table_args__ = (
        Index("ix_model_runs_tenant_scan", "tenant_id", "scan_id"),
        Index("ix_model_runs_revision_branch", "analysis_revision_id", "analysis_branch_result_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    scan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    analysis_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("analysis_revisions.id", ondelete="CASCADE")
    )
    analysis_branch_result_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("analysis_branch_results.id", ondelete="CASCADE")
    )
    retry_number: Mapped[int | None] = mapped_column(Integer)
    image_count: Mapped[int | None] = mapped_column(Integer)
    role_counts: Mapped[dict[str, int] | None] = mapped_column(JSONB)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    cached_tokens: Mapped[int | None] = mapped_column(Integer)
    thought_tokens: Mapped[int | None] = mapped_column(Integer)
    tool_tokens: Mapped[int | None] = mapped_column(Integer)
    response_model_version: Mapped[str | None] = mapped_column(String(100))
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    error_category: Mapped[str | None] = mapped_column(String(100))
    completed_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class EvidenceDossier(Base):
    __tablename__ = "garment_evidence_dossiers"
    __table_args__ = (
        UniqueConstraint("analysis_revision_id", name="uq_evidence_dossiers_revision"),
        Index("ix_evidence_dossiers_tenant_id", "tenant_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    analysis_revision_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analysis_revisions.id", ondelete="CASCADE"), nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class ProposedPlan(Base):
    __tablename__ = "proposed_care_plans"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    analysis_revision_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analysis_revisions.id", ondelete="CASCADE"), nullable=False
    )
    retry_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class ValidationReport(Base):
    __tablename__ = "care_validation_reports"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    proposed_plan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("proposed_care_plans.id", ondelete="CASCADE"), nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class CareResult(Base):
    __tablename__ = "care_results"
    __table_args__ = (
        UniqueConstraint("analysis_revision_id", name="uq_care_results_revision"),
        Index("ix_care_results_tenant_id", "tenant_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    analysis_revision_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analysis_revisions.id", ondelete="CASCADE"), nullable=False
    )
    dossier_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("garment_evidence_dossiers.id", ondelete="RESTRICT"), nullable=False
    )
    proposed_plan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("proposed_care_plans.id", ondelete="RESTRICT"), nullable=False
    )
    validation_report_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("care_validation_reports.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class RenderedAnswer(Base):
    __tablename__ = "rendered_answers"
    __table_args__ = (
        UniqueConstraint(
            "care_result_id",
            "language",
            "template_version",
            name="uq_rendered_answers_result_language_template",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    care_result_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("care_results.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[str] = mapped_column(String(2), nullable=False)
    template_version: Mapped[str] = mapped_column(String(50), nullable=False)
    answer: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class GarmentIdentifier(Base):
    __tablename__ = "garment_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "identifier_type", "normalized_value", name="uq_garment_identifiers_exact"
        ),
        Index("ix_garment_identifiers_garment_id", "garment_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    garment_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("garments.id", ondelete="CASCADE"), nullable=False
    )
    identifier_type: Mapped[str] = mapped_column(String(40), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="verified"
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False, server_default="fabricassist")
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    confirmed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    verified_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class GarmentServiceEvent(Base):
    __tablename__ = "garment_service_events"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('planned', 'performed', 'completed')", name="ck_garment_service_events_kind"
        ),
        CheckConstraint(
            "outcome IN ('successful', 'damaging', 'unknown')",
            name="ck_garment_service_events_outcome",
        ),
        CheckConstraint(
            "water_temperature_c BETWEEN 10 AND 95 OR water_temperature_c IS NULL",
            name="ck_garment_service_events_water_temperature",
        ),
        Index("ix_garment_service_events_garment_created", "garment_id", "created_at"),
        Index("ix_garment_service_events_tenant_id", "tenant_id"),
        Index(
            "ix_garment_service_events_tenant_garment_outcome",
            "tenant_id",
            "garment_id",
            "outcome",
            "occurred_at",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    garment_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("garments.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(80), nullable=False, server_default="unknown")
    water_temperature_c: Mapped[int | None] = mapped_column(Integer)
    cycle: Mapped[str | None] = mapped_column(String(80))
    detergent_category: Mapped[str | None] = mapped_column(String(120))
    detergent_text: Mapped[str | None] = mapped_column(String(500))
    stain_products: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    drying_method: Mapped[str | None] = mapped_column(String(80))
    ironing_method: Mapped[str | None] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, server_default="unknown")
    observed_effects: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    confirmed_by: Mapped[str] = mapped_column(String(80), nullable=False, server_default="unknown")
    occurred_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )
    detail_schema_version: Mapped[str] = mapped_column(
        String(80), nullable=False, server_default="service-event-v1"
    )
    detail_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    exact_garment_confirmed: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    invalidated: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    superseded_by_event_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("garment_service_events.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class GarmentIdentityMatchRun(Base):
    __tablename__ = "garment_identity_match_runs"
    __table_args__ = (Index("ix_garment_identity_match_runs_scan", "scan_id"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    scan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    reasons: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class GarmentIdentityCandidate(Base):
    __tablename__ = "garment_identity_candidates"
    __table_args__ = (
        UniqueConstraint("match_run_id", "garment_id", name="uq_garment_identity_candidate_match"),
        Index("ix_garment_identity_candidates_garment", "garment_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    match_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("garment_identity_match_runs.id", ondelete="CASCADE"), nullable=False
    )
    garment_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("garments.id", ondelete="CASCADE"), nullable=False
    )
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    reasons: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class GarmentIdentityConfirmation(Base):
    __tablename__ = "garment_identity_confirmations"
    __table_args__ = (UniqueConstraint("scan_id", name="uq_garment_identity_confirmations_scan"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    scan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    garment_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("garments.id", ondelete="RESTRICT"), nullable=False
    )
    candidate_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("garment_identity_candidates.id", ondelete="SET NULL")
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reasons: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class GarmentObservation(Base):
    __tablename__ = "garment_observations"
    __table_args__ = (
        UniqueConstraint(
            "analysis_revision_id",
            "projection_key",
            name="uq_garment_observations_revision_projection",
        ),
        Index("ix_garment_observations_garment_created", "garment_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    garment_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("garments.id", ondelete="CASCADE"), nullable=False
    )
    analysis_revision_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analysis_revisions.id", ondelete="CASCADE"), nullable=False
    )
    observation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    projection_key: Mapped[str] = mapped_column(
        String(160), nullable=False, server_default="legacy"
    )
    stability: Mapped[str] = mapped_column(String(20), nullable=False)
    authority: Mapped[str] = mapped_column(String(80), nullable=False, server_default="unknown")
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    supersedes_observation_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("garment_observations.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class ConversationThread(Base):
    __tablename__ = "conversation_threads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "garment_id", name="uq_conversation_threads_tenant_garment"),
        Index("ix_conversation_threads_tenant_user", "tenant_id", "user_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    garment_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("garments.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    active_analysis_revision_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analysis_revisions.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_conversation_messages_role"),
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'blocked', 'needs_review', 'failed')",
            name="ck_conversation_messages_status",
        ),
        UniqueConstraint(
            "thread_id", "idempotency_key", name="uq_conversation_messages_idempotency"
        ),
        Index("ix_conversation_messages_thread_created", "thread_id", "created_at", "id"),
        Index("ix_conversation_messages_tenant_id", "tenant_id"),
        Index(
            "ix_conversation_messages_unpublished",
            "status",
            "dispatch_published_at",
            "created_at",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    thread_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("conversation_threads.id", ondelete="CASCADE"), nullable=False
    )
    scan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    garment_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("garments.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    analysis_revision_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analysis_revisions.id", ondelete="RESTRICT"), nullable=False
    )
    care_result_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("care_results.id", ondelete="RESTRICT"), nullable=False
    )
    model_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("model_runs.id", ondelete="SET NULL")
    )
    actionable_claims: Mapped[dict[str, Any] | list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    evidence_ids: Mapped[dict[str, Any] | list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    uncertainties: Mapped[dict[str, Any] | list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    follow_up_questions: Mapped[dict[str, Any] | list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    validation_report: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(100))
    run_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("ai_runs.id", ondelete="SET NULL"))
    dispatch_correlation_id: Mapped[str] = mapped_column(
        String(36), nullable=False, default="00000000-0000-0000-0000-000000000000"
    )
    dispatch_published_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    completed_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"
    __table_args__ = (
        UniqueConstraint("thread_id", "version", name="uq_conversation_summaries_thread_version"),
        Index("ix_conversation_summaries_tenant_thread", "tenant_id", "thread_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    thread_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("conversation_threads.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    through_message_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("conversation_messages.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class ProductProfile(Base):
    __tablename__ = "product_profiles"
    __table_args__ = (Index("ix_product_profiles_tenant_id", "tenant_id"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(Text)
    license_name: Mapped[str | None] = mapped_column(String(255))
    variant_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    retrieved_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )
    invalidated_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)


class ProductIdentifier(Base):
    __tablename__ = "product_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "product_profile_id", "normalized_value", name="uq_product_identifiers_profile_value"
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    product_profile_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("product_profiles.id", ondelete="CASCADE"), nullable=False
    )
    identifier_type: Mapped[str] = mapped_column(String(40), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(32), nullable=False)


class ProductLookupRun(Base):
    __tablename__ = "product_lookup_runs"
    __table_args__ = (Index("ix_product_lookup_runs_tenant_barcode", "tenant_id", "barcode"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    scan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    analysis_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("analysis_revisions.id", ondelete="SET NULL")
    )
    barcode: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    schema_version: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="product-lookup-v2"
    )
    product_profile_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("product_profiles.id", ondelete="SET NULL")
    )
    safe_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    validated_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )
    refreshed_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    invalidated_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    invalidation_reason: Mapped[str | None] = mapped_column(String(100))


class EvidenceCacheEntry(Base):
    """Durable exact normalized-image extraction cache; pHash is candidate-only."""

    __tablename__ = "evidence_cache_entries"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "normalized_sha256",
            "role",
            "normalization_version",
            "schema_version",
            "prompt_version",
            "provider",
            "model",
            name="uq_evidence_cache_exact_versioned",
        ),
        Index("ix_evidence_cache_tenant_phash", "tenant_id", "perceptual_hash"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    normalized_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    perceptual_hash: Mapped[str] = mapped_column(String(16), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    delta_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_image_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("scan_images.id", ondelete="RESTRICT"), nullable=False
    )
    reuse_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )
    last_reused_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)


class CanonicalPlanCache(Base):
    """Durable signature/provenance record; a signature never bypasses validation."""

    __tablename__ = "canonical_plan_cache_entries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "signature", name="uq_canonical_plan_cache_tenant_signature"),
        Index("ix_canonical_plan_cache_tenant_result", "tenant_id", "care_result_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    signature: Mapped[str] = mapped_column(String(64), nullable=False)
    care_result_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("care_results.id", ondelete="CASCADE"), nullable=False
    )
    evidence_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    proposal_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    validator_version: Mapped[str] = mapped_column(String(64), nullable=False)
    product_fingerprint: Mapped[str | None] = mapped_column(String(64))
    reuse_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )
    last_reused_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)


class RenderedAnswerCache(Base):
    """Durable language/template render cache keyed by a canonical safety signature."""

    __tablename__ = "rendered_answer_cache_entries"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "canonical_signature",
            "language",
            "template_version",
            name="uq_render_cache_versioned",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    canonical_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str] = mapped_column(String(2), nullable=False)
    template_version: Mapped[str] = mapped_column(String(64), nullable=False)
    answer: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_care_result_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("care_results.id", ondelete="RESTRICT"), nullable=False
    )
    reuse_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )
    last_reused_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)


class ReviewCase(Base):
    """Operator-owned review state; analysis artifacts themselves stay immutable."""

    __tablename__ = "review_cases"
    __table_args__ = (
        UniqueConstraint("analysis_revision_id", name="uq_review_cases_revision"),
        CheckConstraint(
            "status IN ('open', 'assigned', 'corrected', 'approved', 'closed')",
            name="ck_review_cases_status",
        ),
        Index("ix_review_cases_tenant_status_created", "tenant_id", "status", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    scan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    garment_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("garments.id", ondelete="SET NULL")
    )
    analysis_revision_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analysis_revisions.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    assigned_operator_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_result_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("care_results.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class EvidenceCorrection(Base):
    """An append-only human assertion, linked to the corrected successor revision."""

    __tablename__ = "evidence_corrections"
    __table_args__ = (
        CheckConstraint(
            "source IN ('customer', 'operator', 'system')", name="ck_evidence_corrections_source"
        ),
        CheckConstraint(
            "confirmation IN ('pending_review', 'accepted', 'rejected')",
            name="ck_evidence_corrections_confirmation",
        ),
        Index("ix_evidence_corrections_tenant_revision", "tenant_id", "corrected_revision_id"),
        Index(
            "ix_evidence_corrections_tenant_original_field",
            "tenant_id",
            "original_revision_id",
            "field_path",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    review_case_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("review_cases.id", ondelete="CASCADE")
    )
    original_revision_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analysis_revisions.id", ondelete="RESTRICT"), nullable=False
    )
    corrected_revision_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analysis_revisions.id", ondelete="RESTRICT"), nullable=False
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    correction: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    field_path: Mapped[str] = mapped_column(String(160), nullable=False, server_default="unknown")
    previous_value: Mapped[Any | None] = mapped_column(JSONB)
    corrected_value: Mapped[Any | None] = mapped_column(JSONB)
    source_image_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("scan_images.id", ondelete="SET NULL")
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="operator")
    confirmation: Mapped[str] = mapped_column(String(20), nullable=False, server_default="accepted")
    supersedes_correction_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("evidence_corrections.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class EvidenceConflictRecord(Base):
    """Immutable v2 conflict projection; branch payloads remain untouched."""

    __tablename__ = "evidence_conflicts"
    __table_args__ = (
        CheckConstraint("char_length(field_path) >= 1", name="ck_evidence_conflicts_field_path"),
        UniqueConstraint(
            "analysis_revision_id",
            "field_path",
            "resolution_code",
            name="uq_evidence_conflicts_revision_field_resolution",
        ),
        Index("ix_evidence_conflicts_tenant_revision", "tenant_id", "analysis_revision_id"),
        Index("ix_evidence_conflicts_tenant_safety", "tenant_id", "safety_critical"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    analysis_revision_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analysis_revisions.id", ondelete="CASCADE"), nullable=False
    )
    field_path: Mapped[str] = mapped_column(String(160), nullable=False)
    values: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    selected_value: Mapped[Any | None] = mapped_column(JSONB)
    resolution_code: Mapped[str] = mapped_column(String(120), nullable=False)
    explanation_key: Mapped[str] = mapped_column(String(120), nullable=False)
    safety_critical: Mapped[bool] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class CustomerFeedback(Base):
    __tablename__ = "customer_feedback"
    __table_args__ = (Index("ix_customer_feedback_tenant_scan", "tenant_id", "scan_id"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    scan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    rating: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    request_review: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class DeletionRequest(Base):
    """Durable deletion state, separate from transient object-store execution."""

    __tablename__ = "deletion_requests"
    __table_args__ = (
        CheckConstraint(
            "resource_type IN ('scan', 'garment', 'image')",
            name="ck_deletion_requests_resource_type",
        ),
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed')",
            name="ck_deletion_requests_status",
        ),
        UniqueConstraint(
            "tenant_id", "resource_type", "resource_id", name="uq_deletion_requests_resource"
        ),
        Index("ix_deletion_requests_status_requested", "status", "requested_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    resource_type: Mapped[str] = mapped_column(String(20), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued")
    requested_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)


class ObjectDeletionOutbox(Base):
    __tablename__ = "object_deletion_outbox"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_object_deletion_outbox_status",
        ),
        UniqueConstraint("deletion_request_id", "object_key", name="uq_object_deletion_outbox_key"),
        Index("ix_object_deletion_outbox_status_created", "status", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    deletion_request_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("deletion_requests.id", ondelete="CASCADE"), nullable=False
    )
    image_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("scan_images.id", ondelete="SET NULL")
    )
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    deleted_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_tenant_created", "tenant_id", "created_at"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class AiRun(Base):
    """Durable client-visible lifecycle for one analysis or conversation command."""

    __tablename__ = "ai_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_ai_runs_status",
        ),
        UniqueConstraint(
            "tenant_id", "operation", "idempotency_key", name="uq_ai_runs_idempotency"
        ),
        Index("ix_ai_runs_tenant_user_created", "tenant_id", "user_id", "created_at"),
        Index("ix_ai_runs_scan_status", "scan_id", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    scan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("ai_runs.id", ondelete="SET NULL")
    )
    cancel_requested_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    started_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    completed_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    error_code: Mapped[str | None] = mapped_column(String(100))
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AiRunImage(Base):
    """The completed scan images explicitly associated with an AI run."""

    __tablename__ = "ai_run_images"
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("ai_runs.id", ondelete="CASCADE"), primary_key=True
    )
    image_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("scan_images.id", ondelete="RESTRICT"), primary_key=True
    )


class AiRunEvent(Base):
    """Replayable durable SSE event; heartbeats are intentionally not stored."""

    __tablename__ = "ai_run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_ai_run_events_sequence"),
        Index("ix_ai_run_events_run_sequence", "run_id", "sequence"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("ai_runs.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )
