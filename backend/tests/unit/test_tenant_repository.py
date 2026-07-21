"""Unit tests for the intentionally transaction-neutral tenant repository."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.infrastructure.persistence.models import Tenant
from fabricassist.infrastructure.persistence.repositories import TenantRepository


class RecordingSession:
    """Minimal async-session substitute that records transaction-affecting calls."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.committed = False
        self.rolled_back = False

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def get(self, _model: type[object], _identifier: object) -> None:
        return None

    async def execute(self, _statement: object) -> Any:
        raise AssertionError("This test only exercises add().")

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


async def test_add_leaves_commit_or_rollback_to_the_caller() -> None:
    session = RecordingSession()
    repository = TenantRepository(cast(AsyncSession, session))
    tenant = Tenant(slug="rollback-tenant", name="Rollback Tenant")

    await repository.add(tenant)
    await session.rollback()

    assert session.added == [tenant]
    assert session.committed is False
    assert session.rolled_back is True
