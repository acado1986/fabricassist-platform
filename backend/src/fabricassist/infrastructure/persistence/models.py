"""Baseline persistence schema; it deliberately contains no authentication behavior."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
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
    __table_args__ = (
        Index("ix_garments_tenant_id", "tenant_id"),
        Index("ix_garments_merged_into_id", "merged_into_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    active_analysis_revision_id: Mapped[UUID | None] = mapped_column(Uuid)
    active_result_id: Mapped[UUID | None] = mapped_column(Uuid)
    merged_into_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("garments.id", ondelete="RESTRICT")
    )
    merged_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class AnalysisRevision(Base):
    __tablename__ = "analysis_revisions"
    __table_args__ = (
        UniqueConstraint("scan_id", "revision_number", name="uq_analysis_revisions_scan_number"),
        Index("ix_analysis_revisions_tenant_id", "tenant_id"),
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


class ModelRun(Base):
    __tablename__ = "model_runs"
    __table_args__ = (Index("ix_model_runs_tenant_scan", "tenant_id", "scan_id"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    scan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
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
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    error_category: Mapped[str | None] = mapped_column(String(100))
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
        Index("ix_garment_service_events_garment_created", "garment_id", "created_at"),
        Index("ix_garment_service_events_tenant_id", "tenant_id"),
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
    __table_args__ = (Index("ix_garment_observations_garment_created", "garment_id", "created_at"),)
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
    stability: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
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
    barcode: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    schema_version: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="product-lookup-v1"
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
        Index("ix_evidence_corrections_tenant_revision", "tenant_id", "corrected_revision_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    review_case_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("review_cases.id", ondelete="CASCADE"), nullable=False
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
