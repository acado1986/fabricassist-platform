from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image

from fabricassist.application.analysis import analyse_scan
from fabricassist.infrastructure.persistence.models import (
    AnalysisRevision,
    CareResult,
    Garment,
    GarmentIdentifier,
    RevisionImage,
    Scan,
    ScanImage,
)
from fabricassist.infrastructure.vision.providers.mock import MockModelProviderAdapter
from fabricassist.settings import Settings


class ScalarRows:
    def __init__(self, values: Sequence[object]) -> None:
        self._values = values

    def all(self) -> list[object]:
        return list(self._values)


class FakeSession:
    def __init__(self, scan: Scan, images: list[ScanImage]) -> None:
        self.scan = scan
        self.images = images
        self.added: list[object] = []
        self.committed = False

    async def get(self, model: type[object], identifier: object) -> Scan | None:
        assert model is Scan
        assert identifier == self.scan.id
        return self.scan

    async def scalars(self, statement: object) -> ScalarRows:
        return ScalarRows(self.images)

    async def scalar(self, statement: object) -> int:
        return 0

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


class FakeSessionFactory:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    def __call__(self) -> AbstractAsyncContextManager[FakeSession]:
        session = self._session

        class Context(AbstractAsyncContextManager[FakeSession]):
            async def __aenter__(self) -> FakeSession:
                return session

            async def __aexit__(self, *args: object) -> None:
                return None

        return Context()


class FakeDatabase:
    def __init__(self, session: FakeSession) -> None:
        self.session_factory = FakeSessionFactory(session)


class FakeStorage:
    def __init__(self, image: bytes) -> None:
        self._image = image

    def read_object(self, key: str) -> bytes:
        return self._image


def image_bytes() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (400, 400), "white").save(stream, "JPEG")
    return stream.getvalue()


@pytest.mark.asyncio
async def test_worker_creates_tenant_owned_revision_membership_and_activates_result() -> None:
    tenant_id = uuid4()
    scan = Scan(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=uuid4(),
        status="queued",
        requested_language="en",
    )
    image = ScanImage(
        id=uuid4(),
        tenant_id=tenant_id,
        scan_id=scan.id,
        role="care_label",
        display_order=0,
        object_key="private/test/image",
        upload_token=uuid4(),
        upload_expires_at=datetime.now(UTC) + timedelta(minutes=1),
        completed_at=datetime.now(UTC),
    )
    session = FakeSession(scan, [image])

    await analyse_scan(
        database=FakeDatabase(session),  # type: ignore[arg-type]
        storage=FakeStorage(image_bytes()),  # type: ignore[arg-type]
        settings=Settings(environment="test", vision_provider="mock"),
        scan_id=scan.id,
        model_provider=MockModelProviderAdapter(),
    )

    memberships = [value for value in session.added if isinstance(value, RevisionImage)]
    revisions = [value for value in session.added if isinstance(value, AnalysisRevision)]
    results = [value for value in session.added if isinstance(value, CareResult)]
    garments = [value for value in session.added if isinstance(value, Garment)]
    identifiers = [value for value in session.added if isinstance(value, GarmentIdentifier)]
    assert len(memberships) == len(revisions) == len(results) == 1
    assert len(garments) == len(identifiers) == 1
    assert identifiers[0].garment_id == garments[0].id
    assert scan.garment_id == garments[0].id
    assert memberships[0].tenant_id == tenant_id
    assert memberships[0].image_id == image.id
    assert scan.active_analysis_revision_id == revisions[0].id
    assert scan.active_result_id == results[0].id
    assert scan.analysis_stage == "completed"
    assert session.committed
