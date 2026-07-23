"""Baseline persistence schema; it deliberately contains no authentication behavior."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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
    status: Mapped[str] = mapped_column(String(30), nullable=False)
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
