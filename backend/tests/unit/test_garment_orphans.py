from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.api.routes.garments import archive_if_orphaned
from fabricassist.infrastructure.persistence.models import Garment


class ScalarSession:
    def __init__(self, value: int) -> None:
        self.value = value

    async def scalar(self, _statement: object) -> int:
        return self.value


@pytest.mark.asyncio
async def test_archive_orphaned_garment_hides_superseded_record() -> None:
    garment = Garment(id=uuid4(), tenant_id=uuid4(), user_id=uuid4())

    archived = await archive_if_orphaned(
        cast(AsyncSession, ScalarSession(0)),
        garment=garment,
        excluding_scan_id=uuid4(),  # type: ignore[arg-type]
    )

    assert archived is True
    assert garment.archived_at is not None


@pytest.mark.asyncio
async def test_shared_garment_is_not_archived_when_another_scan_references_it() -> None:
    garment = Garment(id=uuid4(), tenant_id=uuid4(), user_id=uuid4())

    archived = await archive_if_orphaned(
        cast(AsyncSession, ScalarSession(1)),
        garment=garment,
        excluding_scan_id=uuid4(),  # type: ignore[arg-type]
    )

    assert archived is False
    assert garment.archived_at is None
