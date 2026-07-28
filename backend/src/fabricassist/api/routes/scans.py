"""Breaking revision-aware scan image collection API."""
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.analysis import TEMPLATE_VERSION, render_rich_result
from fabricassist.application.jobs import AnalysisJobMessage
from fabricassist.application.lifecycle import enqueue_deletion, ensure_review_case
from fabricassist.domain.care import CareValidationReport, ProposedCarePlan
from fabricassist.domain.evidence import GarmentEvidenceDossier, ImageRole
from fabricassist.domain.identity import GarmentIdentifierType, normalize_instance_identifier
from fabricassist.infrastructure.persistence.models import (
    AnalysisJobOperation,
    CareResult,
    CustomerFeedback,
    Garment,
    GarmentIdentifier,
    IdempotencyRecord,
    RenderedAnswer,
    Scan,
    ScanImage,
    User,
)
from fabricassist.infrastructure.storage.s3 import S3Storage
from fabricassist.settings import JobDispatcherType, Settings

router = APIRouter(prefix="/api/v1/scans", tags=["scans"])
Mime = Literal["image/jpeg", "image/png", "image/webp"]


class CreateScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_language: Literal["en", "es"] = "en"
    fabricassist_identifier: str | None = Field(default=None, min_length=3, max_length=255)


class ImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: ImageRole
    content_type: Mime
    display_order: int = Field(default=0, ge=0)


class UploadInstruction(BaseModel):
    image_id: UUID
    role: ImageRole
    url: str
    headers: dict[str, str]
    expires_at: datetime


class ScanResponse(BaseModel):
    scan_id: UUID
    garment_id: UUID | None = None
    status: str
    images_completed: int
    progress_percent: int
    analysis_stage: str | None = None
    error_code: str | None = None


class CreateScanResponse(BaseModel):
    scan_id: UUID
    status: str


class AnalysisResponse(BaseModel):
    scan_id: UUID
    status: str
    operation_key: str


class ResultResponse(BaseModel):
    scan_id: UUID
    status: str
    result: dict[str, object]


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)
    request_review: bool = False


class FeedbackResponse(BaseModel):
    id: UUID
    review_case_id: UUID | None = None


class DeletionResponse(BaseModel):
    id: UUID
    status: str


class ImagePreviewResponse(BaseModel):
    image_id: UUID
    url: str
    expires_at: datetime


async def get_session() -> AsyncSession:
    raise RuntimeError("Database session dependency was not configured.")


async def get_current_user() -> User:
    raise RuntimeError("Authentication dependency was not configured.")


async def get_storage() -> S3Storage:
    raise RuntimeError("Storage dependency was not configured.")


async def get_settings() -> Settings:
    raise RuntimeError("Settings dependency was not configured.")


async def owned_scan(
    session: AsyncSession, user: User, scan_id: UUID, *, for_update: bool = False
) -> Scan:
    statement = select(Scan).where(
        Scan.id == scan_id, Scan.tenant_id == user.tenant_id, Scan.user_id == user.id
    )
    if for_update:
        statement = statement.with_for_update()
    scan = await session.scalar(statement)
    if scan is None:
        raise HTTPException(404, "Scan was not found.")
    return scan


@router.post("", response_model=CreateScanResponse, status_code=201)
async def create_scan(
    request: CreateScanRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> CreateScanResponse:
    garment_id = None
    if request.fabricassist_identifier:
        identifier = await session.scalar(
            select(GarmentIdentifier).where(
                GarmentIdentifier.tenant_id == user.tenant_id,
                GarmentIdentifier.identifier_type
                == GarmentIdentifierType.FABRICASSIST_SERIAL.value,
                GarmentIdentifier.normalized_value
                == normalize_instance_identifier(request.fabricassist_identifier),
                GarmentIdentifier.verification_status == "verified",
            )
        )
        if identifier is not None:
            garment = await session.scalar(
                select(Garment).where(
                    Garment.id == identifier.garment_id,
                    Garment.tenant_id == user.tenant_id,
                    Garment.user_id == user.id,
                )
            )
            if garment is not None:
                garment_id = garment.id
    scan = Scan(
        id=uuid4(),
        tenant_id=user.tenant_id,
        user_id=user.id,
        status="draft",
        requested_language=request.requested_language,
        garment_id=garment_id,
    )
    session.add(scan)
    await session.commit()
    return CreateScanResponse(scan_id=scan.id, status=scan.status)


@router.post("/{scan_id}/images", response_model=UploadInstruction, status_code=201)
async def add_image(
    scan_id: UUID,
    request: ImageRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[S3Storage, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> UploadInstruction:
    scan = await owned_scan(session, user, scan_id)
    if scan.status not in {"draft", "uploading"}:
        raise HTTPException(409, "Images cannot be added after analysis begins.")
    fingerprint = hashlib.sha256(
        json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    operation = f"scan-image:{scan.id}"
    if idempotency_key:
        existing = await session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == user.tenant_id,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise HTTPException(409, "Idempotency key was already used for another request.")
            image_id = UUID(str((existing.response_body or {}).get("image_id", "")))
            image = await session.scalar(
                select(ScanImage).where(
                    ScanImage.id == image_id,
                    ScanImage.scan_id == scan.id,
                    ScanImage.tenant_id == user.tenant_id,
                )
            )
            if image is None:
                raise HTTPException(409, "Idempotency record no longer has an active image.")
            url, headers, expires = storage.presign_put(
                key=image.object_key, content_type=request.content_type
            )
            return UploadInstruction(
                image_id=image.id,
                role=ImageRole(image.role),
                url=url,
                headers=headers,
                expires_at=expires,
            )
    completed = (
        await session.scalar(
            select(func.count())
            .select_from(ScanImage)
            .where(ScanImage.scan_id == scan.id, ScanImage.completed_at.is_not(None))
        )
        or 0
    )
    pending = (
        await session.scalar(
            select(func.count())
            .select_from(ScanImage)
            .where(ScanImage.scan_id == scan.id, ScanImage.completed_at.is_(None))
        )
        or 0
    )
    if completed + pending >= settings.max_images_per_scan:
        raise HTTPException(422, "Maximum image count reached.")
    image_id = uuid4()
    key = f"private/{user.tenant_id}/{scan.id}/{image_id}/original"
    image = ScanImage(
        id=image_id,
        tenant_id=user.tenant_id,
        scan_id=scan.id,
        role=request.role.value,
        display_order=request.display_order,
        object_key=key,
        upload_token=uuid4(),
        upload_expires_at=datetime.now(UTC),
    )
    session.add(image)
    url, headers, expires = storage.presign_put(key=key, content_type=request.content_type)
    image.upload_expires_at = expires
    if idempotency_key:
        session.add(
            IdempotencyRecord(
                id=uuid4(),
                tenant_id=user.tenant_id,
                user_id=user.id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                response_status=201,
                response_body={"image_id": str(image.id)},
                expires_at=expires,
            )
        )
    scan.status = "uploading"
    await session.commit()
    return UploadInstruction(
        image_id=image.id, role=request.role, url=url, headers=headers, expires_at=expires
    )


@router.delete(
    "/{scan_id}/images/{image_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
)
async def remove_image(
    scan_id: UUID,
    image_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[S3Storage, Depends(get_storage)],
) -> Response:
    await owned_scan(session, user, scan_id)
    image = await session.scalar(
        select(ScanImage).where(
            ScanImage.id == image_id,
            ScanImage.scan_id == scan_id,
            ScanImage.tenant_id == user.tenant_id,
        )
    )
    if image is None:
        raise HTTPException(404, "Image was not found.")
    storage.delete_object(image.object_key)
    await session.delete(image)
    await session.commit()
    return Response(status_code=204)


class CompleteUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_id: UUID
    content_type: Mime


@router.post("/{scan_id}/uploads/complete", response_model=ScanResponse)
async def complete_upload(
    scan_id: UUID,
    request: CompleteUploadRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[S3Storage, Depends(get_storage)],
) -> ScanResponse:
    scan = await owned_scan(session, user, scan_id)
    image = await session.scalar(
        select(ScanImage).where(ScanImage.id == request.image_id, ScanImage.scan_id == scan.id)
    )
    if image is None:
        raise HTTPException(404, "Image was not found.")
    if image.completed_at is None:
        metadata = storage.verify_image(image.object_key, request.content_type)
        image.mime_type = metadata.content_type
        image.byte_size = metadata.byte_size
        image.width = metadata.width
        image.height = metadata.height
        image.completed_at = datetime.now(UTC)
        await session.commit()
    return await scan_detail(scan_id, session, user)


@router.post("/{scan_id}/analyse", response_model=AnalysisResponse, status_code=202)
async def request_analysis(
    scan_id: UUID,
    http_request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AnalysisResponse:
    scan = await owned_scan(
        session,
        user,
        scan_id,
        for_update=settings.job_dispatcher == JobDispatcherType.QSTASH,
    )
    count = (
        await session.scalar(
            select(func.count())
            .select_from(ScanImage)
            .where(ScanImage.scan_id == scan.id, ScanImage.completed_at.is_not(None))
        )
        or 0
    )
    if not count:
        raise HTTPException(409, "Complete at least one image before analysis.")
    key = idempotency_key or f"scan:{scan.id}"
    if settings.job_dispatcher == JobDispatcherType.QSTASH:
        existing_operation = await session.scalar(
            select(AnalysisJobOperation).where(
                AnalysisJobOperation.scan_id == scan.id,
                AnalysisJobOperation.operation_key == key,
            )
        )
        if existing_operation is not None:
            return AnalysisResponse(
                scan_id=scan.id,
                status=scan.status,
                operation_key=existing_operation.operation_key,
            )
    scan.analysis_operation_key = key
    scan.status = "queued"
    scan.analysis_stage = "queued"
    if settings.job_dispatcher == JobDispatcherType.QSTASH:
        # This durable row is the redispatch record: if publication fails after
        # this commit, the reconciler can safely publish the same message.
        revision_id = uuid4()
        operation = AnalysisJobOperation(
            id=uuid4(),
            scan_id=scan.id,
            revision_id=revision_id,
            operation_key=key,
            stage="validate_uploaded_images",
        )
        session.add(operation)
        await session.commit()
        from fabricassist.infrastructure.jobs.factory import create_job_dispatcher

        dispatcher = create_job_dispatcher(settings)
        await dispatcher.dispatch_analysis(
            AnalysisJobMessage(
                scan_id=scan.id,
                operation_key=key,
                revision_id=revision_id,
                stage="validate_uploaded_images",
            ),
            correlation_id=str(http_request.state.correlation_id),
        )
        operation.published_at = datetime.now(UTC)
        await session.commit()
    else:
        await session.commit()
        from fabricassist.worker.celery_app import celery_app

        celery_app.send_task(
            "fabricassist.analyse_scan",
            args=[str(scan.id)],
            headers={"correlation_id": str(http_request.state.correlation_id)},
        )
    return AnalysisResponse(scan_id=scan.id, status=scan.status, operation_key=key)


@router.get("/{scan_id}", response_model=ScanResponse)
async def scan_detail(
    scan_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> ScanResponse:
    scan = await owned_scan(session, user, scan_id)
    completed = (
        await session.scalar(
            select(func.count())
            .select_from(ScanImage)
            .where(ScanImage.scan_id == scan.id, ScanImage.completed_at.is_not(None))
        )
        or 0
    )
    return ScanResponse(
        scan_id=scan.id,
        garment_id=scan.garment_id,
        status=scan.status,
        images_completed=completed,
        progress_percent=scan.progress_percent,
        analysis_stage=scan.analysis_stage,
        error_code=scan.analysis_error_code,
    )


@router.get("/{scan_id}/result", response_model=ResultResponse)
async def scan_result(
    scan_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    language: Literal["en", "es"] = "en",
) -> ResultResponse:
    scan = await owned_scan(session, user, scan_id)
    if scan.active_result_id is None:
        raise HTTPException(409, "Analysis result is not available yet.")
    result = await session.get(CareResult, scan.active_result_id)
    if result is None:
        raise HTTPException(409, "Analysis result is not available yet.")
    rendered = await session.scalar(
        select(RenderedAnswer).where(
            RenderedAnswer.care_result_id == result.id,
            RenderedAnswer.language == language,
            RenderedAnswer.template_version == TEMPLATE_VERSION,
        )
    )
    if rendered is None:
        canonical = result.canonical_data
        answer = render_rich_result(
            GarmentEvidenceDossier.model_validate(canonical["dossier"]),
            ProposedCarePlan.model_validate(canonical["proposal"]),
            CareValidationReport.model_validate(canonical["validation"]),
            language,
        )
        rendered = RenderedAnswer(
            id=uuid4(),
            tenant_id=result.tenant_id,
            care_result_id=result.id,
            language=language,
            template_version=TEMPLATE_VERSION,
            answer=answer,
        )
        session.add(rendered)
        await session.commit()
    return ResultResponse(
        scan_id=scan.id,
        status=result.status,
        result=rendered.answer if rendered else result.canonical_data,
    )


@router.post("/{scan_id}/feedback", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(
    scan_id: UUID,
    request: FeedbackRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> FeedbackResponse:
    scan = await owned_scan(session, user, scan_id)
    feedback = CustomerFeedback(
        id=uuid4(),
        tenant_id=user.tenant_id,
        scan_id=scan.id,
        user_id=user.id,
        rating=request.rating,
        comment=request.comment,
        request_review=request.request_review,
    )
    session.add(feedback)
    review_id = None
    if request.request_review:
        review = await ensure_review_case(session, scan)
        review_id = review.id
        scan.status = "needs_review"
    await session.commit()
    return FeedbackResponse(id=feedback.id, review_case_id=review_id)


@router.get("/{scan_id}/images/{image_id}/preview", response_model=ImagePreviewResponse)
async def image_preview(
    scan_id: UUID,
    image_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[S3Storage, Depends(get_storage)],
) -> ImagePreviewResponse:
    scan = await owned_scan(session, user, scan_id)
    image = await session.scalar(
        select(ScanImage).where(
            ScanImage.id == image_id,
            ScanImage.scan_id == scan.id,
            ScanImage.tenant_id == user.tenant_id,
            ScanImage.deleted_at.is_(None),
        )
    )
    if image is None:
        raise HTTPException(404, "Image was not found.")
    url, expires_at = storage.presign_get(key=image.object_key)
    return ImagePreviewResponse(image_id=image.id, url=url, expires_at=expires_at)


@router.delete("/{scan_id}", response_model=DeletionResponse, status_code=202)
async def delete_scan(
    scan_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> DeletionResponse:
    scan = await owned_scan(session, user, scan_id)
    images = list(
        (
            await session.scalars(
                select(ScanImage).where(
                    ScanImage.scan_id == scan.id, ScanImage.deleted_at.is_(None)
                )
            )
        ).all()
    )
    request = await enqueue_deletion(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        resource_type="scan",
        resource_id=scan.id,
        images=images,
    )
    scan.status = "deleted"
    scan.user_id = None
    scan.garment_id = None
    await session.commit()
    return DeletionResponse(id=request.id, status=request.status)
