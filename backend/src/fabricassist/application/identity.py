"""Application use cases for confirming remembered-garment identity."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.lifecycle import audit
from fabricassist.infrastructure.persistence.models import (
    AnalysisRevision,
    ConversationThread,
    Garment,
    GarmentIdentityCandidate,
    GarmentObservation,
    GarmentServiceEvent,
    ReviewCase,
    Scan,
    User,
)


async def merge_confirmed_garment(
    session: AsyncSession,
    *,
    scan: Scan,
    target: Garment,
    candidate: GarmentIdentityCandidate,
    actor: User,
) -> UUID | None:
    """Attach a confirmed scan and soft-delete its temporary source garment.

    Analysis artifacts belong to the physical garment, not to the temporary
    garment created before identity confirmation. The operation is called
    inside the confirmation transaction, so a failure leaves both records
    unchanged.
    """
    source_id = scan.garment_id
    if source_id is None or source_id == target.id:
        scan.garment_id = target.id
        return None

    source = await session.scalar(
        select(Garment)
        .where(
            Garment.id == source_id,
            Garment.tenant_id == actor.tenant_id,
            Garment.user_id == actor.id,
        )
        .with_for_update()
    )
    if source is None:
        raise ValueError("The source garment for this scan no longer exists.")

    revisions = list(
        (
            await session.scalars(
                select(AnalysisRevision).where(
                    AnalysisRevision.scan_id == scan.id,
                    AnalysisRevision.garment_id == source.id,
                )
            )
        ).all()
    )
    revision_ids = [revision.id for revision in revisions]
    for revision in revisions:
        revision.garment_id = target.id

    if revision_ids:
        observations = list(
            (
                await session.scalars(
                    select(GarmentObservation).where(
                        GarmentObservation.analysis_revision_id.in_(revision_ids),
                        GarmentObservation.garment_id == source.id,
                    )
                )
            ).all()
        )
        for observation in observations:
            observation.garment_id = target.id

        reviews = list(
            (
                await session.scalars(
                    select(ReviewCase).where(
                        ReviewCase.analysis_revision_id.in_(revision_ids),
                        ReviewCase.garment_id == source.id,
                    )
                )
            ).all()
        )
        for review in reviews:
            review.garment_id = target.id

    scan.garment_id = target.id
    if scan.active_analysis_revision_id is not None:
        target.active_analysis_revision_id = scan.active_analysis_revision_id
    if scan.active_result_id is not None:
        target.active_result_id = scan.active_result_id

    source.active_analysis_revision_id = None
    source.active_result_id = None

    other_scans = list(
        (
            await session.scalars(
                select(Scan.id).where(
                    Scan.garment_id == source.id,
                    Scan.id != scan.id,
                    Scan.tenant_id == actor.tenant_id,
                )
            )
        ).all()
    )
    other_revisions = list(
        (
            await session.scalars(
                select(AnalysisRevision.id).where(AnalysisRevision.garment_id == source.id)
            )
        ).all()
    )
    service_events = await session.scalar(
        select(GarmentServiceEvent.id).where(GarmentServiceEvent.garment_id == source.id).limit(1)
    )
    conversation = await session.scalar(
        select(ConversationThread.id).where(ConversationThread.garment_id == source.id).limit(1)
    )
    source_can_be_merged = (
        not other_scans and not other_revisions and service_events is None and conversation is None
    )
    if source_can_be_merged:
        source.merged_into_id = target.id
        source.merged_at = datetime.now(UTC)

    audit(
        session,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.id,
        event_type="garment.merged",
        resource_type="garment",
        resource_id=target.id,
        safe_metadata={
            "source_garment_id": str(source.id),
            "target_garment_id": str(target.id),
            "candidate_id": str(candidate.id),
            "source_merged": source_can_be_merged,
        },
    )
    return source.id if source_can_be_merged else None
