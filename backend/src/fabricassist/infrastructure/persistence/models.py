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
        CheckConstraint("kind IN ('garment', 'care_label', 'other')", name="ck_scan_images_kind"),
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
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
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


class ModelRun(Base):
    """Safe audit metadata for one provider invocation; private prompt/image bodies are excluded."""

    __tablename__ = "model_runs"
    __table_args__ = (Index("ix_model_runs_tenant_scan", "tenant_id", "scan_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"))
    scan_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("scans.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd_micros: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class LabelExtraction(Base):
    """Validated language-independent extraction facts and original visible text."""

    __tablename__ = "label_extractions"
    __table_args__ = (
        UniqueConstraint("scan_id", name="uq_label_extractions_scan"),
        Index("ix_label_extractions_tenant_id", "tenant_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"))
    scan_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("scans.id", ondelete="CASCADE"))
    model_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("model_runs.id", ondelete="SET NULL")
    )
    original_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    validated_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class CareResult(Base):
    """Canonical deterministic care outcome; no provider prose is stored here."""

    __tablename__ = "care_results"
    __table_args__ = (
        UniqueConstraint("scan_id", name="uq_care_results_scan"),
        Index("ix_care_results_tenant_id", "tenant_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"))
    scan_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("scans.id", ondelete="CASCADE"))
    extraction_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("label_extractions.id", ondelete="SET NULL")
    )
    canonical_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rules_version: Mapped[str] = mapped_column(String(50), nullable=False)
    detergent_rules_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )


class RenderedAnswer(Base):
    """Durable localized rendering of a canonical result."""

    __tablename__ = "rendered_answers"
    __table_args__ = (
        UniqueConstraint(
            "care_result_id",
            "language",
            "template_version",
            name="uq_rendered_answers_result_language_template",
        ),
        Index("ix_rendered_answers_tenant_id", "tenant_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"))
    care_result_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("care_results.id", ondelete="CASCADE")
    )
    language: Mapped[str] = mapped_column(String(2), nullable=False)
    template_version: Mapped[str] = mapped_column(String(50), nullable=False)
    answer: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcTimestamp, nullable=False, server_default=func.now()
    )
