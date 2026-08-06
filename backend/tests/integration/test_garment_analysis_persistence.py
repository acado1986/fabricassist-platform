# pyright: reportPrivateUsage=false
"""PostgreSQL concurrency coverage for the Phase 4 branch-state adapter."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import cast
from uuid import UUID, uuid4

import pytest
from PIL import Image
from sqlalchemy import func, select

from fabricassist.application.garment_analysis.commands import AnalysisBranch
from fabricassist.application.garment_analysis.ports import (
    BranchCompletion,
    BranchInvocation,
    ProviderImage,
)
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.garment_analysis.persistence import (
    SqlAlchemyGarmentAnalysisRepository,
    SqlAlchemyV2EvidenceCacheRepository,
)
from fabricassist.infrastructure.operational_metrics import durable_metrics
from fabricassist.infrastructure.persistence.models import (
    AnalysisBranchResult,
    AnalysisRevision,
    EvidenceCacheEntry,
    Garment,
    GarmentIdentityCandidate,
    GarmentIdentityMatchRun,
    ModelRun,
    Scan,
    ScanImage,
    Tenant,
    User,
)


class _MemoryHotCache:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, object]] = {}

    async def get_json(self, key: str) -> dict[str, object] | None:
        value = self.values.get(key)
        return dict(value) if value is not None else None

    async def set_json(self, key: str, value: dict[str, object], *, ttl_seconds: int) -> None:
        assert ttl_seconds > 0
        self.values[key] = dict(value)


def _jpeg(color: str) -> bytes:
    output = BytesIO()
    Image.new("RGB", (64, 64), color).save(output, "JPEG")
    return output.getvalue()


TEST_DATABASE_URL = os.environ.get("FABRICASSIST_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="FABRICASSIST_TEST_DATABASE_URL is required for PostgreSQL branch-state tests.",
)


def _fingerprint(value: str) -> str:
    return value.ljust(64, "0")[:64]


def _test_database_url() -> str:
    assert TEST_DATABASE_URL is not None
    return TEST_DATABASE_URL


async def _create_revision(database: Database) -> tuple[UUID, UUID, UUID]:
    tenant_id = uuid4()
    user_id = uuid4()
    scan_id = uuid4()
    revision_id = uuid4()
    async with database.session_factory() as session, session.begin():
        session.add(
            Tenant(
                id=tenant_id,
                slug=f"branch-{tenant_id.hex[:16]}",
                name="Branch test tenant",
            )
        )
        await session.flush()
        session.add(
            User(
                id=user_id,
                tenant_id=tenant_id,
                email=f"{user_id.hex}@example.test",
                password_hash="x" * 32,
            )
        )
        await session.flush()
        session.add(
            Scan(
                id=scan_id,
                tenant_id=tenant_id,
                user_id=user_id,
                status="processing",
                requested_language="en",
            )
        )
        await session.flush()
        session.add(
            AnalysisRevision(
                id=revision_id,
                tenant_id=tenant_id,
                scan_id=scan_id,
                revision_number=1,
                status="processing",
                module_version="garment-analysis-v2",
                workflow_version="garment-analysis-v2",
                merged_schema_version="merged-assessment-v2",
                care_policy_version="care-policy-v2",
                confidence_policy_version="confidence-policy-v1",
                retry_policy_version="retry-policy-v1",
            )
        )
    return tenant_id, scan_id, revision_id


async def _claim_and_commit(
    database: Database,
    tenant_id: UUID,
    revision_id: UUID,
    *,
    now: datetime,
):
    async with database.session_factory() as session, session.begin():
        return await SqlAlchemyGarmentAnalysisRepository(session).claim_branch(
            tenant_id=tenant_id,
            revision_id=revision_id,
            branch=AnalysisBranch.LABEL_EXTRACTION,
            request_fingerprint=_fingerprint("label"),
            lease_seconds=10,
            now=now,
        )


def test_competing_claims_stale_takeover_and_terminal_skip() -> None:
    assert TEST_DATABASE_URL is not None

    async def scenario() -> None:
        database = Database(_test_database_url())
        try:
            tenant_id, _, revision_id = await _create_revision(database)
            now = datetime.now(UTC)
            first, second = await asyncio.gather(
                _claim_and_commit(database, tenant_id, revision_id, now=now),
                _claim_and_commit(database, tenant_id, revision_id, now=now),
            )
            claims = [claim for claim in (first, second) if claim is not None]
            assert len(claims) == 1
            first_claim = claims[0]

            # A worker that never completes is reclaimable only after its lease.
            stale_claim = await _claim_and_commit(
                database,
                tenant_id,
                revision_id,
                now=now + timedelta(seconds=11),
            )
            assert stale_claim is not None
            assert stale_claim.attempt_number == 2
            assert stale_claim.claim_token != first_claim.claim_token

            async with database.session_factory() as session, session.begin():
                repository = SqlAlchemyGarmentAnalysisRepository(session)
                assert not await repository.complete_branch(
                    tenant_id=tenant_id,
                    claim=first_claim,
                    completion=BranchCompletion(status="completed", result_payload={"stale": True}),
                    now=now + timedelta(seconds=12),
                )
                assert await repository.complete_branch(
                    tenant_id=tenant_id,
                    claim=stale_claim,
                    completion=BranchCompletion(
                        status="completed",
                        result_payload={"label": "validated"},
                        overall_confidence=95,
                        invocation=BranchInvocation(
                            provider="mock",
                            model="mock-v2",
                            prompt_version="label-v2",
                            schema_version="label-extraction-v2",
                            request_fingerprint=_fingerprint("label"),
                            image_count=2,
                            role_counts={"care_label": 1, "composition_label": 1},
                            total_tokens=42,
                        ),
                    ),
                    now=now + timedelta(seconds=12),
                )

            assert (
                await _claim_and_commit(
                    database,
                    tenant_id,
                    revision_id,
                    now=now + timedelta(seconds=30),
                )
                is None
            )
            async with database.session_factory() as session:
                branch = await session.scalar(
                    select(AnalysisBranchResult).where(
                        AnalysisBranchResult.analysis_revision_id == revision_id
                    )
                )
                assert branch is not None
                assert branch.status == "completed"
                assert branch.attempt_count == 2
                assert branch.result_payload == {"label": "validated"}
                assert (
                    await session.scalar(
                        select(func.count(ModelRun.id)).where(
                            ModelRun.analysis_branch_result_id == branch.id
                        )
                    )
                    == 1
                )
        finally:
            await database.close()

    asyncio.run(scenario())


def test_branch_claims_are_tenant_scoped_and_transactional() -> None:
    assert TEST_DATABASE_URL is not None

    async def scenario() -> None:
        database = Database(_test_database_url())
        try:
            tenant_id, _, revision_id = await _create_revision(database)
            now = datetime.now(UTC)
            assert await _claim_and_commit(database, uuid4(), revision_id, now=now) is None

            with pytest.raises(RuntimeError, match="force rollback"):
                async with database.session_factory() as session, session.begin():
                    repository = SqlAlchemyGarmentAnalysisRepository(session)
                    claim = await repository.claim_branch(
                        tenant_id=tenant_id,
                        revision_id=revision_id,
                        branch=AnalysisBranch.GARMENT_INSPECTION,
                        request_fingerprint=_fingerprint("garment"),
                        lease_seconds=10,
                        now=now,
                    )
                    assert claim is not None
                    assert await repository.complete_branch(
                        tenant_id=tenant_id,
                        claim=claim,
                        completion=BranchCompletion(
                            status="completed",
                            result_payload={"garment": "validated"},
                            invocation=BranchInvocation(
                                provider="mock",
                                model="mock-v2",
                                prompt_version="inspection-v2",
                                schema_version="garment-inspection-v2",
                                request_fingerprint=_fingerprint("garment"),
                                image_count=1,
                                role_counts={"garment_overview": 1},
                            ),
                        ),
                    )
                    raise RuntimeError("force rollback")

            async with database.session_factory() as session:
                assert (
                    await session.scalar(
                        select(func.count(AnalysisBranchResult.id)).where(
                            AnalysisBranchResult.analysis_revision_id == revision_id
                        )
                    )
                    == 0
                )
                assert (
                    await session.scalar(
                        select(func.count(ModelRun.id)).where(
                            ModelRun.analysis_revision_id == revision_id
                        )
                    )
                    == 0
                )
        finally:
            await database.close()

    asyncio.run(scenario())


def test_multi_image_cache_uses_postgres_authority_and_valkey_hot_payloads() -> None:
    assert TEST_DATABASE_URL is not None

    async def scenario() -> None:
        database = Database(_test_database_url())
        try:
            tenant_id, scan_id, _ = await _create_revision(database)
            now = datetime.now(UTC)
            first_id, second_id = uuid4(), uuid4()
            first_bytes, second_bytes = _jpeg("red"), _jpeg("blue")
            async with database.session_factory() as session, session.begin():
                session.add_all(
                    [
                        ScanImage(
                            id=first_id,
                            tenant_id=tenant_id,
                            scan_id=scan_id,
                            role="garment_overview",
                            object_key=f"tests/{first_id}.jpg",
                            upload_expires_at=now + timedelta(hours=1),
                            completed_at=now,
                            mime_type="image/jpeg",
                            byte_size=len(first_bytes),
                        ),
                        ScanImage(
                            id=second_id,
                            tenant_id=tenant_id,
                            scan_id=scan_id,
                            role="garment_overview",
                            object_key=f"tests/{second_id}.jpg",
                            upload_expires_at=now + timedelta(hours=1),
                            completed_at=now,
                            mime_type="image/jpeg",
                            byte_size=len(second_bytes),
                        ),
                    ]
                )
            images = (
                ProviderImage(first_id, first_bytes, "garment_overview"),
                ProviderImage(second_id, second_bytes, "garment_overview"),
            )
            hot_cache = _MemoryHotCache()
            repository = SqlAlchemyV2EvidenceCacheRepository(
                database.session_factory
            ).with_hot_cache(hot_cache, ttl_seconds=60)
            await repository.store_branch_result(
                tenant_id=tenant_id,
                branch=AnalysisBranch.GARMENT_INSPECTION,
                images=images,
                provider="mock",
                model="mock-v2",
                prompt_version="inspection-v2",
                schema_version="inspection-v2",
                payload={"marker": "durable"},
            )
            hot_cache.values.clear()
            assert await repository.get_branch_result(
                tenant_id=tenant_id,
                branch=AnalysisBranch.GARMENT_INSPECTION,
                images=images,
                provider="mock",
                model="mock-v2",
                prompt_version="inspection-v2",
                schema_version="inspection-v2",
            ) == {
                "_cache_source": "postgres_exact",
                "marker": "durable",
            }
            assert len(hot_cache.values) == 1

            hot_cache.values[next(iter(hot_cache.values))] = {"marker": "hot"}
            assert await repository.get_branch_result(
                tenant_id=tenant_id,
                branch=AnalysisBranch.GARMENT_INSPECTION,
                images=images,
                provider="mock",
                model="mock-v2",
                prompt_version="inspection-v2",
                schema_version="inspection-v2",
            ) == {
                "_cache_source": "valkey_hot",
                "marker": "hot",
            }

            missing_tenant_id = uuid4()
            missing_key = repository._hot_key(
                tenant_id=missing_tenant_id,
                branch=AnalysisBranch.GARMENT_INSPECTION,
                images=images,
                provider="mock",
                model="mock-v2",
                prompt_version="inspection-v2",
                schema_version="inspection-v2",
            )
            hot_cache.values[missing_key] = {"marker": "orphaned-hot-value"}
            assert (
                await repository.get_branch_result(
                    tenant_id=missing_tenant_id,
                    branch=AnalysisBranch.GARMENT_INSPECTION,
                    images=images,
                    provider="mock",
                    model="mock-v2",
                    prompt_version="inspection-v2",
                    schema_version="inspection-v2",
                )
                is None
            )

            assert repository._cache_sha(images) != repository._cache_sha(tuple(reversed(images)))
            async with database.session_factory() as session:
                entry = await session.scalar(
                    select(EvidenceCacheEntry).where(
                        EvidenceCacheEntry.tenant_id == tenant_id,
                        EvidenceCacheEntry.role == AnalysisBranch.GARMENT_INSPECTION.value,
                    )
                )
                assert entry is not None
                assert entry.reuse_count == 2
        finally:
            await database.close()

    asyncio.run(scenario())


def test_visual_identity_candidates_are_scoped_confirmation_only_and_reject_false_positives() -> (
    None
):
    assert TEST_DATABASE_URL is not None

    async def scenario() -> None:
        from fabricassist.infrastructure.garment_analysis.persistence import (
            SqlAlchemyGarmentAnalysisFinalizationRepository,
        )

        database = Database(_test_database_url())
        try:
            tenant_id, current_scan_id, _ = await _create_revision(database)
            now = datetime.now(UTC)
            async with database.session_factory() as session, session.begin():
                current_scan = await session.get(Scan, current_scan_id)
                assert current_scan is not None and current_scan.user_id is not None
                user_id = current_scan.user_id
                matching_garment = Garment(
                    id=uuid4(), tenant_id=tenant_id, user_id=user_id, display_name="match"
                )
                matching_garment_id = matching_garment.id
                false_positive_garment = Garment(
                    id=uuid4(), tenant_id=tenant_id, user_id=user_id, display_name="different"
                )
                session.add_all((matching_garment, false_positive_garment))
                await session.flush()

                matching_scan = Scan(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    user_id=user_id,
                    garment_id=matching_garment.id,
                    status="completed",
                    requested_language="en",
                )
                false_positive_scan = Scan(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    user_id=user_id,
                    garment_id=false_positive_garment.id,
                    status="completed",
                    requested_language="en",
                )
                session.add_all((matching_scan, false_positive_scan))
                await session.flush()

                other_tenant_id, other_user_id = uuid4(), uuid4()
                session.add(
                    Tenant(
                        id=other_tenant_id,
                        slug=f"visual-{other_tenant_id.hex[:16]}",
                        name="Other visual tenant",
                    )
                )
                await session.flush()
                session.add(
                    User(
                        id=other_user_id,
                        tenant_id=other_tenant_id,
                        email=f"{other_user_id.hex}@example.test",
                        password_hash="x" * 32,
                    )
                )
                await session.flush()
                other_garment = Garment(
                    id=uuid4(), tenant_id=other_tenant_id, user_id=other_user_id
                )
                session.add(other_garment)
                await session.flush()
                other_scan = Scan(
                    id=uuid4(),
                    tenant_id=other_tenant_id,
                    user_id=other_user_id,
                    garment_id=other_garment.id,
                    status="completed",
                    requested_language="en",
                )
                session.add(other_scan)
                await session.flush()

                image_specs = (
                    (current_scan_id, tenant_id, "0" * 16, "a" * 64),
                    (matching_scan.id, tenant_id, "0" * 15 + "1", "b" * 64),
                    (false_positive_scan.id, tenant_id, "f" * 16, "c" * 64),
                    (other_scan.id, other_tenant_id, "0" * 16, "d" * 64),
                )
                session.add_all(
                    ScanImage(
                        id=uuid4(),
                        tenant_id=image_tenant_id,
                        scan_id=scan_id,
                        role="garment_overview",
                        object_key=f"tests/{scan_id}.jpg",
                        upload_expires_at=now + timedelta(hours=1),
                        completed_at=now,
                        mime_type="image/jpeg",
                        byte_size=100,
                        normalized_sha256=normalized_sha,
                        perceptual_hash=phash,
                    )
                    for scan_id, image_tenant_id, phash, normalized_sha in image_specs
                )
                await SqlAlchemyGarmentAnalysisFinalizationRepository(
                    session
                )._record_exact_image_candidates(current_scan)

            async with database.session_factory() as session:
                match_run = await session.scalar(
                    select(GarmentIdentityMatchRun).where(
                        GarmentIdentityMatchRun.scan_id == current_scan_id
                    )
                )
                assert match_run is not None
                assert match_run.classification == "visual_candidate"
                candidates = list(
                    (
                        await session.scalars(
                            select(GarmentIdentityCandidate).where(
                                GarmentIdentityCandidate.match_run_id == match_run.id
                            )
                        )
                    ).all()
                )
                assert [(candidate.garment_id, candidate.status) for candidate in candidates] == [
                    (matching_garment_id, "pending")
                ]
                assert candidates[0].reasons["source"] == "perceptual_hash_candidate"
        finally:
            await database.close()

    asyncio.run(scenario())


def test_durable_metrics_expose_v2_cache_observation_and_rendering_outcomes() -> None:
    assert TEST_DATABASE_URL is not None

    async def scenario() -> None:
        database = Database(_test_database_url())
        try:
            async with database.session_factory() as session:
                output = (await durable_metrics(session)).decode()
            assert "fabricassist_analysis_cache_durable_total" in output
            assert "fabricassist_garment_observations_durable_total" in output
            assert "fabricassist_rendered_answers_durable_total" in output
        finally:
            await database.close()

    asyncio.run(scenario())


def test_deterministic_finalization_is_idempotent_and_never_needs_a_planning_run() -> None:
    assert TEST_DATABASE_URL is not None

    async def scenario() -> None:
        from fabricassist.application.garment_analysis.queries import AnalysisReference
        from fabricassist.domain.garment_analysis.models import (
            EvidenceCertainty,
            EvidenceSourceKind,
            FieldEvidence,
            LabelExtraction,
            Permission,
            WashInstruction,
        )
        from fabricassist.infrastructure.garment_analysis.persistence import (
            SqlAlchemyGarmentAnalysisFinalizationRepository,
        )
        from fabricassist.infrastructure.persistence.models import CareResult

        database = Database(_test_database_url())
        try:
            tenant_id, scan_id, revision_id = await _create_revision(database)
            label_evidence = FieldEvidence(
                field_path="care.wash",
                source_kind=EvidenceSourceKind.PHOTOGRAPHED_LABEL,
                source_image_ids=(uuid4(),),
                certainty=EvidenceCertainty.OBSERVED,
                confidence=99,
            )
            label = LabelExtraction(
                wash=WashInstruction(
                    permission=Permission.ALLOWED,
                    maximum_temperature_c=30,
                    evidence=label_evidence,
                ),
                overall_confidence=99,
            )
            async with database.session_factory() as session, session.begin():
                session.add_all(
                    (
                        AnalysisBranchResult(
                            id=uuid4(),
                            tenant_id=tenant_id,
                            analysis_revision_id=revision_id,
                            branch_name="garment_inspection",
                            status="not_provided",
                            attempt_count=0,
                            uncertain_fields=[],
                        ),
                        AnalysisBranchResult(
                            id=uuid4(),
                            tenant_id=tenant_id,
                            analysis_revision_id=revision_id,
                            branch_name="label_extraction",
                            status="completed",
                            attempt_count=1,
                            schema_version="label-extraction-v2",
                            result_payload=label.model_dump(mode="json"),
                            uncertain_fields=[],
                        ),
                    )
                )
            reference = AnalysisReference(
                tenant_id=tenant_id,
                scan_id=scan_id,
                run_id=uuid4(),
                revision_id=revision_id,
            )
            async with database.session_factory() as session, session.begin():
                first = await SqlAlchemyGarmentAnalysisFinalizationRepository(
                    session
                ).finalize_if_ready(reference=reference)
                assert first is not None
                assert first.status == "passed"
                assert "garment_analysis_result" in first.canonical_data
            from fabricassist.domain.garment_analysis.models import StainTreatment

            async with database.session_factory() as session, session.begin():
                session.add(
                    AnalysisBranchResult(
                        id=uuid4(),
                        tenant_id=tenant_id,
                        analysis_revision_id=revision_id,
                        branch_name="stain_treatment",
                        status="completed",
                        attempt_count=1,
                        schema_version="stain-treatment-v2",
                        result_payload=StainTreatment(
                            treatment_id=uuid4(), overall_confidence=40
                        ).model_dump(mode="json"),
                        uncertain_fields=["stain_identity_unconfirmed"],
                    )
                )
            async with database.session_factory() as session, session.begin():
                second = await SqlAlchemyGarmentAnalysisFinalizationRepository(
                    session
                ).finalize_if_ready(reference=reference)
                assert second is not None
                assert second.canonical_data != first.canonical_data
                canonical = cast(
                    dict[str, object], second.canonical_data["garment_analysis_result"]
                )
                validated = cast(dict[str, object], canonical["validated_stain_treatment"])
                assert validated["outcome"] == "passed"
            async with database.session_factory() as session:
                assert (
                    await session.scalar(
                        select(func.count(CareResult.id)).where(
                            CareResult.analysis_revision_id == revision_id
                        )
                    )
                    == 1
                )
                assert (
                    await session.scalar(
                        select(func.count(ModelRun.id)).where(
                            ModelRun.analysis_revision_id == revision_id,
                            ModelRun.operation == "care_planning",
                        )
                    )
                    == 0
                )
        finally:
            await database.close()

    asyncio.run(scenario())
