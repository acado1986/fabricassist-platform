"""Operator review boundary; it exposes artifacts without provider internals."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.lifecycle import apply_human_correction, audit
from fabricassist.application.planning import CarePlanningProvider
from fabricassist.domain.evidence import GarmentEvidenceDossier
from fabricassist.infrastructure.persistence.models import (
    CareResult,
    EvidenceDossier,
    GarmentServiceEvent,
    ProposedPlan,
    ReviewCase,
    Scan,
    User,
    ValidationReport,
)

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


class ReviewResponse(BaseModel):
    id: UUID
    scan_id: UUID
    analysis_revision_id: UUID
    status: str
    assigned_operator_id: UUID | None
    approved_result_id: UUID | None


class ReviewDetail(ReviewResponse):
    dossier: dict[str, object]
    proposal: dict[str, object]
    validation: dict[str, object]


class CorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dossier: GarmentEvidenceDossier
    reason: str = Field(min_length=3, max_length=2000)


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_note: str | None = Field(default=None, max_length=1000)


class ConfirmServiceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(pattern="^(performed|completed)$")
    note: str | None = Field(default=None, max_length=1000)


async def get_session() -> AsyncSession:
    raise RuntimeError("Database session dependency was not configured.")


async def get_current_user() -> User:
    raise RuntimeError("Authentication dependency was not configured.")


async def get_care_planning_provider() -> CarePlanningProvider:
    raise RuntimeError("Care-planning provider dependency was not configured.")


def require_operator(user: User) -> None:
    if user.role not in {"operator", "admin"}:
        raise HTTPException(403, "Operator access is required.")


async def case_for(session: AsyncSession, user: User, review_id: UUID) -> ReviewCase:
    review = await session.scalar(
        select(ReviewCase).where(ReviewCase.id == review_id, ReviewCase.tenant_id == user.tenant_id)
    )
    if review is None:
        raise HTTPException(404, "Review case was not found.")
    return review


def response(review: ReviewCase) -> ReviewResponse:
    return ReviewResponse(
        id=review.id,
        scan_id=review.scan_id,
        analysis_revision_id=review.analysis_revision_id,
        status=review.status,
        assigned_operator_id=review.assigned_operator_id,
        approved_result_id=review.approved_result_id,
    )


@router.get("", response_model=list[ReviewResponse])
async def list_reviews(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[ReviewResponse]:
    require_operator(user)
    cases = list(
        (
            await session.scalars(
                select(ReviewCase)
                .where(
                    ReviewCase.tenant_id == user.tenant_id,
                    ReviewCase.status.in_(("open", "assigned", "corrected")),
                )
                .order_by(ReviewCase.created_at)
            )
        ).all()
    )
    return [response(review) for review in cases]


@router.get("/{review_id}", response_model=ReviewDetail)
async def review_detail(
    review_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> ReviewDetail:
    require_operator(user)
    review = await case_for(session, user, review_id)
    result = await session.scalar(
        select(CareResult).where(CareResult.analysis_revision_id == review.analysis_revision_id)
    )
    if result is None:
        raise HTTPException(409, "Review artifacts are unavailable.")
    dossier = await session.get(EvidenceDossier, result.dossier_id)
    plan = await session.get(ProposedPlan, result.proposed_plan_id)
    validation = await session.get(ValidationReport, result.validation_report_id)
    if dossier is None or plan is None or validation is None:
        raise HTTPException(409, "Review artifacts are unavailable.")
    return ReviewDetail(
        **response(review).model_dump(),
        dossier=dossier.payload,
        proposal=plan.payload,
        validation=validation.payload,
    )


@router.post("/{review_id}/assign", response_model=ReviewResponse)
async def assign_review(
    review_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> ReviewResponse:
    require_operator(user)
    review = await case_for(session, user, review_id)
    if review.assigned_operator_id not in {None, user.id}:
        raise HTTPException(409, "Review case is assigned to another operator.")
    review.assigned_operator_id = user.id
    review.status = "assigned"
    audit(
        session,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        event_type="review.assigned",
        resource_type="review_case",
        resource_id=review.id,
    )
    await session.commit()
    return response(review)


@router.post("/{review_id}/corrections", response_model=ReviewResponse)
async def correct_review(
    review_id: UUID,
    request: CorrectionRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    care_planning_provider: Annotated[
        CarePlanningProvider,
        Depends(get_care_planning_provider),
    ],
) -> ReviewResponse:
    require_operator(user)
    review = await case_for(session, user, review_id)
    if review.assigned_operator_id not in {None, user.id}:
        raise HTTPException(409, "Review case is assigned to another operator.")
    result = await apply_human_correction(
        session,
        review=review,
        actor_id=user.id,
        dossier=request.dossier,
        reason=request.reason,
        care_planning_provider=care_planning_provider,
    )
    await session.commit()
    # The correction is a successor revision; approval never erases source artifacts.
    review.approved_result_id = None
    _ = result
    return response(review)


@router.post("/{review_id}/approve", response_model=ReviewResponse)
async def approve_review(
    review_id: UUID,
    request: ApprovalRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReviewResponse:
    require_operator(user)
    review = await case_for(session, user, review_id)
    if review.status == "approved":
        return response(review)
    scan = await session.get(Scan, review.scan_id)
    if scan is None or scan.active_result_id is None:
        raise HTTPException(409, "A corrected result is required before approval.")
    review.approved_result_id = scan.active_result_id
    review.status = "approved"
    scan.status = "completed"
    audit(
        session,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        event_type="review.approved",
        resource_type="review_case",
        resource_id=review.id,
        safe_metadata={
            "has_customer_note": bool(request.customer_note),
            "idempotency_key_present": idempotency_key is not None,
        },
    )
    await session.commit()
    return response(review)


@router.post("/{review_id}/service-events", status_code=201)
async def confirm_service_event(
    review_id: UUID,
    request: ConfirmServiceRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """Only staff-confirmed events can make a garment appear cleaned-before."""
    require_operator(user)
    review = await case_for(session, user, review_id)
    if review.garment_id is None:
        raise HTTPException(409, "This review is not linked to a garment.")
    event = GarmentServiceEvent(
        tenant_id=user.tenant_id,
        garment_id=review.garment_id,
        user_id=user.id,
        kind=request.kind,
        note=request.note,
    )
    session.add(event)
    audit(
        session,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        event_type="service.confirmed",
        resource_type="garment_service_event",
        resource_id=event.id,
        safe_metadata={"kind": request.kind},
    )
    await session.commit()
    return {"id": str(event.id), "kind": event.kind}
