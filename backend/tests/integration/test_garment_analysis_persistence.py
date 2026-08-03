"""PostgreSQL concurrency coverage for the Phase 4 branch-state adapter."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from fabricassist.application.garment_analysis.commands import AnalysisBranch
from fabricassist.application.garment_analysis.ports import (
    BranchCompletion,
    BranchInvocation,
)
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.garment_analysis.persistence import (
    SqlAlchemyGarmentAnalysisRepository,
)
from fabricassist.infrastructure.persistence.models import (
    AnalysisBranchResult,
    AnalysisRevision,
    ModelRun,
    Scan,
    Tenant,
    User,
)

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
