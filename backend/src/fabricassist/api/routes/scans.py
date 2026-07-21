"""Tenant-protected direct upload endpoints for Phase 7."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.analysis import render_result
from fabricassist.infrastructure.persistence.models import (
    CareResult,
    RenderedAnswer,
    Scan,
    ScanImage,
    User,
)
from fabricassist.infrastructure.storage.s3 import S3Storage

router = APIRouter(prefix="/api/v1/scans", tags=["scans"])


class CreateScanImageRequest(BaseModel):
    kind: Literal["garment", "care_label"]
    content_type: Literal["image/jpeg", "image/png", "image/webp"]


class CreateScanRequest(BaseModel):
    images: list[CreateScanImageRequest] = Field(min_length=1, max_length=2)
    requested_language: Literal["en", "es"] = "en"

    @model_validator(mode="after")
    def require_distinct_image_roles(self) -> CreateScanRequest:
        roles = [image.kind for image in self.images]
        if len(set(roles)) != len(roles):
            raise ValueError("Provide at most one image for each role.")
        return self


class UploadInstruction(BaseModel):
    upload_id: UUID
    kind: Literal["garment", "care_label"]
    url: str
    headers: dict[str, str]
    expires_at: datetime


class CreateScanResponse(BaseModel):
    scan_id: UUID
    status: str
    uploads: list[UploadInstruction]


class CompleteUploadRequest(BaseModel):
    upload_id: UUID
    content_type: Literal["image/jpeg", "image/png", "image/webp"]


class ScanResponse(BaseModel):
    scan_id: UUID
    status: str
    images_completed: int
    progress_percent: int = 0
    analysis_stage: str | None = None
    error_code: str | None = None


class AnalysisResponse(BaseModel):
    scan_id: UUID
    status: str
    operation_key: str


class ResultResponse(BaseModel):
    scan_id: UUID
    status: str
    answer: dict[str, object]


async def get_session() -> AsyncSession:
    raise RuntimeError("Database session dependency was not configured.")


async def get_current_user() -> User:
    raise RuntimeError("Authentication dependency was not configured.")


async def get_storage() -> S3Storage:
    raise RuntimeError("Storage dependency was not configured.")


@router.post("", response_model=CreateScanResponse, status_code=201)
async def create_scan(
    request: CreateScanRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[S3Storage, Depends(get_storage)],
) -> CreateScanResponse:
    scan = Scan(
        id=uuid4(),
        tenant_id=user.tenant_id,
        user_id=user.id,
        status="uploading",
        requested_language=request.requested_language,
    )
    session.add(scan)
    await session.flush()
    uploads: list[UploadInstruction] = []
    for requested_image in request.images:
        image_id = uuid4()
        object_key = f"tenants/{user.tenant_id}/scans/{scan.id}/images/{image_id}"
        image = ScanImage(
            id=image_id,
            tenant_id=user.tenant_id,
            scan_id=scan.id,
            kind=requested_image.kind,
            object_key=object_key,
            upload_token=uuid4(),
            upload_expires_at=datetime.now(UTC),
        )
        session.add(image)
        url, headers, expires_at = storage.presign_put(
            key=object_key, content_type=requested_image.content_type
        )
        image.upload_expires_at = expires_at
        uploads.append(
            UploadInstruction(
                upload_id=image.upload_token,
                kind=requested_image.kind,
                url=url,
                headers=headers,
                expires_at=expires_at,
            )
        )
    await session.commit()
    return CreateScanResponse(
        scan_id=scan.id,
        status=scan.status,
        uploads=uploads,
    )


@router.post("/{scan_id}/uploads/complete", response_model=ScanResponse)
async def complete_upload(
    scan_id: UUID,
    request: CompleteUploadRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[S3Storage, Depends(get_storage)],
) -> ScanResponse:
    image = await session.scalar(
        select(ScanImage).where(
            ScanImage.scan_id == scan_id,
            ScanImage.tenant_id == user.tenant_id,
            ScanImage.upload_token == request.upload_id,
        )
    )
    if image is None:
        raise HTTPException(status_code=404, detail="Upload was not found.")
    if image.completed_at is not None:
        return await scan_detail(scan_id, session, user)
    if image.upload_expires_at < datetime.now(UTC):
        raise HTTPException(status_code=400, detail="Upload instruction expired.")
    try:
        metadata = storage.verify_image(image.object_key, request.content_type)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    image.mime_type, image.byte_size, image.width, image.height = (
        metadata.content_type,
        metadata.byte_size,
        metadata.width,
        metadata.height,
    )
    image.completed_at = datetime.now(UTC)
    await session.commit()
    return await scan_detail(scan_id, session, user)


@router.post("/{scan_id}/analyse", response_model=AnalysisResponse, status_code=202)
async def request_analysis(
    scan_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AnalysisResponse:
    """Queue the operation once; worker delivery is idempotent through persisted scan state."""
    scan = await session.scalar(
        select(Scan).where(Scan.id == scan_id, Scan.tenant_id == user.tenant_id)
    )
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan was not found.")
    completed_kinds = set(
        (
            await session.scalars(
                select(ScanImage.kind).where(
                    ScanImage.scan_id == scan.id, ScanImage.completed_at.is_not(None)
                )
            )
        ).all()
    )
    if not completed_kinds:
        raise HTTPException(
            status_code=409,
            detail="Complete at least one image before analysis.",
        )
    operation_key = idempotency_key or f"scan:{scan.id}"
    if scan.analysis_operation_key not in (None, operation_key):
        raise HTTPException(
            status_code=409, detail="A different analysis operation already exists."
        )
    scan.analysis_operation_key = operation_key
    if scan.status not in {"processing", "completed", "needs_review", "needs_better_image"}:
        scan.status, scan.analysis_stage, scan.progress_percent = "queued", "queued", 0
    await session.commit()
    if scan.status == "queued":
        from fabricassist.worker.celery_app import celery_app

        celery_app.send_task("fabricassist.analyse_scan", args=[str(scan.id)])  # pyright: ignore[reportUnknownMemberType]
    return AnalysisResponse(scan_id=scan.id, status=scan.status, operation_key=operation_key)


@router.get("/{scan_id}", response_model=ScanResponse)
async def scan_detail(
    scan_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> ScanResponse:
    scan = await session.scalar(
        select(Scan).where(Scan.id == scan_id, Scan.tenant_id == user.tenant_id)
    )
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan was not found.")
    completed = await session.scalar(
        select(func.count())
        .select_from(ScanImage)
        .where(ScanImage.scan_id == scan.id, ScanImage.completed_at.is_not(None))
    )
    return ScanResponse(
        scan_id=scan.id,
        status=scan.status,
        images_completed=completed or 0,
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
    scan = await session.scalar(
        select(Scan).where(Scan.id == scan_id, Scan.tenant_id == user.tenant_id)
    )
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan was not found.")
    result = await session.scalar(select(CareResult).where(CareResult.scan_id == scan.id))
    if result is None:
        raise HTTPException(status_code=409, detail="Analysis result is not available yet.")
    rendered = await session.scalar(
        select(RenderedAnswer).where(
            RenderedAnswer.care_result_id == result.id,
            RenderedAnswer.language == language,
            RenderedAnswer.template_version == "result-v1",
        )
    )
    if rendered is None:
        rendered = RenderedAnswer(
            tenant_id=scan.tenant_id,
            care_result_id=result.id,
            language=language,
            template_version="result-v1",
            answer=render_result(result.canonical_data, language),
        )
        session.add(rendered)
        await session.commit()
    return ResultResponse(scan_id=scan.id, status=result.status, answer=rendered.answer)
