"""Unit tests for Phase 5 persistence metadata."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

from fabricassist.infrastructure.persistence.models import Base, Scan, Tenant, User


def test_baseline_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "tenants",
        "users",
        "refresh_sessions",
        "scans",
        "scan_images",
        "idempotency_records",
        "ruleset_versions",
    }


def test_tenant_owned_baseline_tables_have_tenant_id_indexes() -> None:
    for table_name in (
        "users",
        "refresh_sessions",
        "scans",
        "scan_images",
        "idempotency_records",
        "ruleset_versions",
    ):
        table = Base.metadata.tables[table_name]
        assert "tenant_id" in table.c
        assert any("tenant_id" in index.columns.keys() for index in table.indexes)


def test_uuid_and_utc_baseline_columns_are_explicit() -> None:
    assert isinstance(Tenant.__table__.c.id.type, PostgreSQLUUID)
    assert Tenant.__table__.c.id.type.as_uuid is True
    assert isinstance(Scan.__table__.c.created_at.type, DateTime)
    assert isinstance(Scan.__table__.c.updated_at.type, DateTime)
    assert Scan.__table__.c.created_at.type.timezone is True
    assert Scan.__table__.c.updated_at.type.timezone is True
    assert isinstance(User.__table__.c.email.type, CITEXT)
    tenant = Tenant(slug="test-tenant", name="Test Tenant")
    assert isinstance(tenant.id, UUID) or tenant.id is None
