from collections.abc import Sequence
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.identity import merge_confirmed_garment
from fabricassist.domain.identity import (
    IdentityClassification,
    ServiceEventKind,
    classify_identifier_match,
    normalize_instance_identifier,
)
from fabricassist.infrastructure.persistence.models import (
    AnalysisRevision,
    Garment,
    GarmentIdentityCandidate,
    GarmentObservation,
    ReviewCase,
    Scan,
    User,
)


def test_only_exact_instance_may_auto_link() -> None:
    assert IdentityClassification.EXACT_INSTANCE.may_auto_link
    assert not IdentityClassification.SAME_PRODUCT.may_auto_link
    assert not IdentityClassification.VISUAL_CANDIDATE.may_auto_link


def test_non_exact_candidates_require_confirmation() -> None:
    assert IdentityClassification.PROBABLE_INSTANCE.requires_confirmation
    assert IdentityClassification.SAME_PRODUCT.requires_confirmation
    assert IdentityClassification.VISUAL_CANDIDATE.requires_confirmation
    assert not IdentityClassification.IDENTITY_CONFLICT.requires_confirmation


def test_only_completed_service_confirms_cleaned_before() -> None:
    assert ServiceEventKind.COMPLETED.confirms_cleaning
    assert not ServiceEventKind.PLANNED.confirms_cleaning
    assert not ServiceEventKind.PERFORMED.confirms_cleaning


def test_verified_identifier_normalization_and_ownership_are_required_for_exact_link() -> None:
    assert normalize_instance_identifier(" fa- 123 ") == "FA-123"
    assert (
        classify_identifier_match(identifier_found=True, owner_matches=True)
        is IdentityClassification.EXACT_INSTANCE
    )
    assert (
        classify_identifier_match(identifier_found=True, owner_matches=False)
        is IdentityClassification.IDENTITY_CONFLICT
    )
    assert (
        classify_identifier_match(identifier_found=False, owner_matches=False)
        is IdentityClassification.NEW_GARMENT
    )


@pytest.mark.asyncio
async def test_confirmed_identity_moves_revision_and_deletes_empty_source_garment() -> None:
    tenant_id = uuid4()
    user_id = uuid4()
    source = Garment(id=uuid4(), tenant_id=tenant_id, user_id=user_id)
    target = Garment(id=uuid4(), tenant_id=tenant_id, user_id=user_id)
    revision = AnalysisRevision(
        id=uuid4(),
        tenant_id=tenant_id,
        scan_id=uuid4(),
        garment_id=source.id,
        revision_number=1,
        status="completed",
    )
    scan = Scan(
        id=revision.scan_id,
        tenant_id=tenant_id,
        user_id=user_id,
        garment_id=source.id,
        active_analysis_revision_id=revision.id,
        active_result_id=uuid4(),
        status="completed",
        requested_language="en",
    )
    observation = GarmentObservation(
        id=uuid4(),
        tenant_id=tenant_id,
        garment_id=source.id,
        analysis_revision_id=revision.id,
        observation_type="material",
        stability="stable",
        value={"value": "wool"},
    )
    review = ReviewCase(
        id=uuid4(),
        tenant_id=tenant_id,
        scan_id=scan.id,
        garment_id=source.id,
        analysis_revision_id=revision.id,
    )
    candidate = GarmentIdentityCandidate(
        id=uuid4(),
        tenant_id=tenant_id,
        match_run_id=uuid4(),
        garment_id=target.id,
        classification=IdentityClassification.PROBABLE_INSTANCE.value,
        reasons={},
    )
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="customer@example.invalid",
        password_hash="not-used",
    )

    class Result:
        def __init__(self, values: Sequence[object]) -> None:
            self.values = list(values)

        def all(self) -> list[object]:
            return self.values

    class Session:
        def __init__(self) -> None:
            self.scalar_values = [source, None, None]
            self.scalars_values = [[revision], [observation], [review], [], []]
            self.deleted: list[object] = []
            self.executed: list[object] = []
            self.added: list[object] = []

        async def scalar(self, _statement: object) -> object | None:
            return self.scalar_values.pop(0)

        async def scalars(self, _statement: object) -> Result:
            return Result(self.scalars_values.pop(0))

        async def execute(self, statement: object) -> None:
            self.executed.append(statement)

        async def delete(self, value: object) -> None:
            self.deleted.append(value)

        def add(self, value: object) -> None:
            self.added.append(value)

    session = Session()
    deleted_id = await merge_confirmed_garment(
        cast(AsyncSession, session),
        scan=scan,
        target=target,
        candidate=candidate,
        actor=user,
    )

    assert deleted_id == source.id
    assert scan.garment_id == target.id
    assert revision.garment_id == target.id
    assert observation.garment_id == target.id
    assert review.garment_id == target.id
    assert target.active_analysis_revision_id == revision.id
    assert target.active_result_id == scan.active_result_id
    assert session.deleted == []
    assert source.merged_into_id == target.id
    assert source.merged_at is not None
