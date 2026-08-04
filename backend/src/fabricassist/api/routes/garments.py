"""Tenant-scoped physical garment history endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.lifecycle import enqueue_deletion
from fabricassist.application.object_storage import ObjectStorage
from fabricassist.application.storefront_queries import (
    GarmentDetailView,
    GarmentHistoryView,
    StorefrontPrincipal,
    StorefrontQueryPort,
)
from fabricassist.domain.identity import IdentityClassification
from fabricassist.infrastructure.persistence.models import (
    AnalysisRevision,
    Garment,
    GarmentIdentifier,
    GarmentIdentityCandidate,
    GarmentIdentityConfirmation,
    GarmentIdentityMatchRun,
    GarmentServiceEvent,
    ProductLookupRun,
    Scan,
    ScanImage,
    User,
)

router = APIRouter(prefix="/api/v1/garments", tags=["garments"])


class ServiceEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["planned", "performed", "completed"]
    note: str | None = Field(default=None, max_length=1000)


class ServiceEventResponse(BaseModel):
    id: UUID
    kind: str
    note: str | None


class GarmentResponse(BaseModel):
    id: UUID
    analysed_before: bool
    cleaned_before: bool
    identifiers: list[str] = Field(default_factory=list)
    last_analysis_at: str | None = None
    thumbnail_url: str | None = None
    service_events: list[ServiceEventResponse]


class IdentityCandidateResponse(BaseModel):
    id: UUID
    garment_id: UUID
    classification: str
    reasons: dict[str, object]
    status: str
    thumbnail_url: str | None = None


class ConfirmCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: UUID


class RejectCandidateRequest(ConfirmCandidateRequest):
    pass


class HistoryResponse(BaseModel):
    garment_id: UUID
    observations: list[dict[str, object]]
    service_events: list[ServiceEventResponse]


class DeletionResponse(BaseModel):
    id: UUID
    status: str


async def get_session() -> AsyncSession:
    raise RuntimeError("Database session dependency was not configured.")


async def get_current_user() -> User:
    raise RuntimeError("Authentication dependency was not configured.")


async def get_storage() -> ObjectStorage:
    raise RuntimeError("Storage dependency was not configured.")


async def get_storefront_queries() -> StorefrontQueryPort:
    raise RuntimeError("Storefront query dependency was not configured.")


def principal_for_user(user: User) -> StorefrontPrincipal:
    return StorefrontPrincipal(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        role=user.role,
        preferred_language=user.preferred_language,
    )


def response_from_detail(detail: GarmentDetailView) -> GarmentResponse:
    return GarmentResponse(
        id=detail.id,
        analysed_before=detail.analysed_before,
        cleaned_before=detail.cleaned_before,
        identifiers=detail.identifiers,
        last_analysis_at=(detail.last_analysis_at.isoformat() if detail.last_analysis_at else None),
        thumbnail_url=detail.thumbnail_url,
        service_events=[
            ServiceEventResponse(id=event.id, kind=event.kind, note=event.note)
            for event in detail.service_events
        ],
    )


def response_from_history(item: GarmentHistoryView) -> GarmentResponse:
    return GarmentResponse(
        id=item.id,
        analysed_before=item.analysed_before,
        cleaned_before=item.cleaned_before,
        identifiers=item.identifiers,
        last_analysis_at=(item.last_analysis_at.isoformat() if item.last_analysis_at else None),
        thumbnail_url=item.thumbnail_url,
        service_events=[
            ServiceEventResponse(id=event.id, kind=event.kind, note=event.note)
            for event in item.service_events
        ],
    )


async def owned_garment(session: AsyncSession, user: User, garment_id: UUID) -> Garment:
    garment = await session.scalar(
        select(Garment).where(
            Garment.id == garment_id,
            Garment.tenant_id == user.tenant_id,
            Garment.user_id == user.id,
            Garment.archived_at.is_(None),
        )
    )
    if garment is None:
        raise HTTPException(404, "Garment was not found.")
    return garment


async def archive_if_orphaned(
    session: AsyncSession,
    *,
    garment: Garment,
    excluding_scan_id: UUID,
) -> bool:
    """Hide a superseded garment only when no live scan still references it."""
    references = await session.scalar(
        select(func.count())
        .select_from(Scan)
        .where(
            Scan.garment_id == garment.id,
            Scan.id != excluding_scan_id,
            Scan.status != "deleted",
            Scan.tenant_id == garment.tenant_id,
        )
    )
    if references:
        return False
    garment.archived_at = datetime.now(UTC)
    return True


async def response_for(
    session: AsyncSession, garment: Garment, storage: ObjectStorage
) -> GarmentResponse:
    events = list(
        (
            await session.scalars(
                select(GarmentServiceEvent)
                .where(GarmentServiceEvent.garment_id == garment.id)
                .order_by(GarmentServiceEvent.created_at.desc())
            )
        ).all()
    )
    identifiers = list(
        (
            await session.scalars(
                select(GarmentIdentifier.normalized_value).where(
                    GarmentIdentifier.tenant_id == garment.tenant_id,
                    GarmentIdentifier.garment_id == garment.id,
                    GarmentIdentifier.verification_status == "verified",
                )
            )
        ).all()
    )
    revision = None
    if garment.active_analysis_revision_id is not None:
        revision = await session.get(AnalysisRevision, garment.active_analysis_revision_id)
    image = await session.scalar(
        select(ScanImage)
        .join(Scan, Scan.id == ScanImage.scan_id)
        .where(
            Scan.tenant_id == garment.tenant_id,
            Scan.user_id == garment.user_id,
            Scan.garment_id == garment.id,
            ScanImage.deleted_at.is_(None),
        )
        .order_by(ScanImage.created_at.desc())
        .limit(1)
    )
    return GarmentResponse(
        id=garment.id,
        analysed_before=garment.active_analysis_revision_id is not None,
        cleaned_before=any(event.kind == "completed" for event in events),
        identifiers=identifiers,
        last_analysis_at=revision.created_at.isoformat()
        if revision and revision.created_at
        else None,
        thumbnail_url=storage.presign_get(key=image.object_key).url if image else None,
        service_events=[ServiceEventResponse(id=e.id, kind=e.kind, note=e.note) for e in events],
    )


@router.get("", response_model=list[GarmentResponse])
async def list_garments(
    user: Annotated[User, Depends(get_current_user)],
    queries: Annotated[StorefrontQueryPort, Depends(get_storefront_queries)],
) -> list[GarmentResponse]:
    items, _ = await queries.list_garment_history(
        principal_for_user(user), first=100_000, after=None
    )
    return [response_from_history(item) for item in items]


@router.get("/{garment_id}", response_model=GarmentResponse)
async def get_garment(
    garment_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    queries: Annotated[StorefrontQueryPort, Depends(get_storefront_queries)],
) -> GarmentResponse:
    detail = await queries.get_garment_detail(
        principal_for_user(user),
        garment_id,
        first=100_000,
        after=None,
        language=user.preferred_language,
    )
    if detail is None:
        raise HTTPException(404, "Garment was not found.")
    return response_from_detail(detail)


@router.post("/{garment_id}/service-events", response_model=ServiceEventResponse, status_code=201)
async def add_service_event(
    garment_id: UUID,
    request: ServiceEventRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> ServiceEventResponse:
    await owned_garment(session, user, garment_id)
    event = GarmentServiceEvent(
        tenant_id=user.tenant_id,
        garment_id=garment_id,
        user_id=user.id,
        kind=request.kind,
        note=request.note,
    )
    session.add(event)
    await session.commit()
    return ServiceEventResponse(id=event.id, kind=event.kind, note=event.note)


@router.delete("/{garment_id}/service-events/{event_id}", status_code=204)
async def delete_service_event(
    garment_id: UUID,
    event_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    event = await session.scalar(select(GarmentServiceEvent).where(
        GarmentServiceEvent.id == event_id,
        GarmentServiceEvent.garment_id == garment_id,
        GarmentServiceEvent.tenant_id == user.tenant_id,
    ))
    if event is None:
        raise HTTPException(404, "Service event was not found.")
    await session.delete(event)
    await session.commit()


@router.get("/{garment_id}/history", response_model=HistoryResponse)
async def garment_history(
    garment_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    queries: Annotated[StorefrontQueryPort, Depends(get_storefront_queries)],
) -> HistoryResponse:
    detail = await queries.get_garment_detail(
        principal_for_user(user),
        garment_id,
        first=100_000,
        after=None,
        language=user.preferred_language,
    )
    if detail is None:
        raise HTTPException(404, "Garment was not found.")
    return HistoryResponse(
        garment_id=detail.id,
        observations=[
            {
                "id": observation.id,
                "type": observation.observation_type,
                "stability": observation.stability,
                "value": observation.value,
                "created_at": observation.created_at.isoformat(),
            }
            for observation in detail.observations
        ],
        service_events=[
            ServiceEventResponse(id=event.id, kind=event.kind, note=event.note)
            for event in detail.service_events
        ],
    )


@router.delete("/{garment_id}", response_model=DeletionResponse, status_code=202)
async def delete_garment(
    garment_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> DeletionResponse:
    garment = await owned_garment(session, user, garment_id)
    scans = list(
        (
            await session.scalars(
                select(Scan).where(Scan.garment_id == garment.id, Scan.tenant_id == user.tenant_id)
            )
        ).all()
    )
    scan_ids = [scan.id for scan in scans]
    images = (
        list(
            (
                await session.scalars(
                    select(ScanImage).where(
                        ScanImage.scan_id.in_(scan_ids), ScanImage.deleted_at.is_(None)
                    )
                )
            ).all()
        )
        if scan_ids
        else []
    )
    request = await enqueue_deletion(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        resource_type="garment",
        resource_id=garment.id,
        images=images,
    )
    for scan in scans:
        scan.status = "deleted"
        scan.user_id = None
        scan.garment_id = None
    if scan_ids:
        runs = list(
            (
                await session.scalars(
                    select(ProductLookupRun).where(ProductLookupRun.scan_id.in_(scan_ids))
                )
            ).all()
        )
        for run in runs:
            await session.delete(run)
    await session.execute(
        delete(GarmentIdentityConfirmation).where(
            GarmentIdentityConfirmation.tenant_id == user.tenant_id,
            GarmentIdentityConfirmation.garment_id == garment.id,
        )
    )
    await session.delete(garment)
    await session.commit()
    return DeletionResponse(id=request.id, status=request.status)


@router.get("/identity-candidates/{scan_id}", response_model=list[IdentityCandidateResponse])
async def identity_candidates(
    scan_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
) -> list[IdentityCandidateResponse]:
    run_ids = select(GarmentIdentityMatchRun.id).where(
        GarmentIdentityMatchRun.tenant_id == user.tenant_id,
        GarmentIdentityMatchRun.scan_id == scan_id,
    )
    candidates = list(
        (
            await session.scalars(
                select(GarmentIdentityCandidate).where(
                    GarmentIdentityCandidate.tenant_id == user.tenant_id,
                    GarmentIdentityCandidate.match_run_id.in_(run_ids),
                )
            )
        ).all()
    )
    responses: list[IdentityCandidateResponse] = []
    for candidate in candidates:
        image = await session.scalar(
            select(ScanImage)
            .join(Scan, Scan.id == ScanImage.scan_id)
            .where(
                Scan.tenant_id == user.tenant_id,
                Scan.user_id == user.id,
                Scan.garment_id == candidate.garment_id,
                ScanImage.deleted_at.is_(None),
            )
            .order_by(ScanImage.created_at.desc())
            .limit(1)
        )
        thumbnail_url = storage.presign_get(key=image.object_key).url if image else None
        responses.append(
            IdentityCandidateResponse(
                id=candidate.id,
                garment_id=candidate.garment_id,
                classification=candidate.classification,
                reasons=candidate.reasons,
                status=candidate.status,
                thumbnail_url=thumbnail_url,
            )
        )
    return responses


@router.post("/identity-candidates/{scan_id}/confirm", response_model=GarmentResponse)
async def confirm_identity_candidate(
    scan_id: UUID,
    request: ConfirmCandidateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
) -> GarmentResponse:
    scan = await session.scalar(
        select(Scan).where(
            Scan.id == scan_id, Scan.tenant_id == user.tenant_id, Scan.user_id == user.id
        )
    )
    candidate = await session.scalar(
        select(GarmentIdentityCandidate).where(
            GarmentIdentityCandidate.id == request.candidate_id,
            GarmentIdentityCandidate.tenant_id == user.tenant_id,
            GarmentIdentityCandidate.match_run_id.in_(
                select(GarmentIdentityMatchRun.id).where(
                    GarmentIdentityMatchRun.scan_id == scan_id,
                    GarmentIdentityMatchRun.tenant_id == user.tenant_id,
                )
            ),
        )
    )
    if (
        scan is None
        or candidate is None
        or candidate.classification
        not in {
            IdentityClassification.PROBABLE_INSTANCE.value,
            IdentityClassification.SAME_PRODUCT.value,
            IdentityClassification.VISUAL_CANDIDATE.value,
        }
    ):
        raise HTTPException(404, "Identity candidate was not found.")
    garment = await owned_garment(session, user, candidate.garment_id)
    existing = await session.scalar(
        select(GarmentIdentityConfirmation).where(GarmentIdentityConfirmation.scan_id == scan.id)
    )
    if existing is not None:
        if existing.garment_id != garment.id:
            raise HTTPException(409, "This scan already has a different confirmed garment.")
        return await response_for(session, garment, storage)
    previous_garment_id = scan.garment_id
    scan.garment_id = garment.id
    if previous_garment_id is not None and previous_garment_id != garment.id:
        previous_garment = await session.scalar(
            select(Garment).where(
                Garment.id == previous_garment_id,
                Garment.tenant_id == user.tenant_id,
            )
        )
        if previous_garment is not None:
            archived = await archive_if_orphaned(
                session,
                garment=previous_garment,
                excluding_scan_id=scan.id,
            )
            if archived:
                previous_garment.merged_into_id = garment.id
                previous_garment.merged_at = datetime.now(UTC)
    candidate.status = "confirmed"
    session.add(
        GarmentIdentityConfirmation(
            tenant_id=user.tenant_id,
            scan_id=scan.id,
            garment_id=garment.id,
            candidate_id=candidate.id,
            actor_user_id=user.id,
            decision="confirmed",
            reasons=candidate.reasons,
        )
    )
    await session.commit()
    return await response_for(session, garment, storage)


@router.post("/identity-candidates/{scan_id}/reject", response_model=IdentityCandidateResponse)
async def reject_identity_candidate(
    scan_id: UUID,
    request: RejectCandidateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> IdentityCandidateResponse:
    """Record a declined candidate without affecting the new scan's garment."""

    candidate = await session.scalar(
        select(GarmentIdentityCandidate).where(
            GarmentIdentityCandidate.id == request.candidate_id,
            GarmentIdentityCandidate.tenant_id == user.tenant_id,
            GarmentIdentityCandidate.match_run_id.in_(
                select(GarmentIdentityMatchRun.id).where(
                    GarmentIdentityMatchRun.scan_id == scan_id,
                    GarmentIdentityMatchRun.tenant_id == user.tenant_id,
                )
            ),
        )
    )
    if candidate is None or candidate.status != "pending":
        raise HTTPException(404, "Pending identity candidate was not found.")
    candidate.status = "rejected"
    await session.commit()
    return IdentityCandidateResponse(
        id=candidate.id,
        garment_id=candidate.garment_id,
        classification=candidate.classification,
        reasons=candidate.reasons,
        status=candidate.status,
    )
