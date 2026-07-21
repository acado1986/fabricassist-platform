"""Narrow persistence repositories for the Phase 5 storage baseline."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.infrastructure.persistence.models import Tenant


class TenantRepository:
    """Persists tenant records without owning transaction boundaries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, tenant: Tenant) -> None:
        """Stage a tenant for the caller's explicit transaction."""
        self._session.add(tenant)

    async def get(self, tenant_id: UUID) -> Tenant | None:
        """Load a tenant by UUID without applying authorization policy."""
        return await self._session.get(Tenant, tenant_id)

    async def get_by_slug(self, slug: str) -> Tenant | None:
        """Load a tenant by its unique slug."""
        result = await self._session.execute(select(Tenant).where(Tenant.slug == slug))
        return result.scalar_one_or_none()
