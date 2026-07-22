"""Breaking revision-aware scan image collection API."""
# pyright: reportUnknownMemberType=false

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.domain.evidence import ImageRole
from fabricassist.infrastructure.persistence.models import (
    CareResult,
    RenderedAnswer,
    Scan,
    ScanImage,
    User,
)
from fabricassist.infrastructure.storage.s3 import S3Storage

router = APIRouter(prefix="/api/v1/scans", tags=["scans"])
Mime = Literal["image/jpeg", "image/png", "image/webp"]


class CreateScanRequest(BaseModel):
    requested_language: Literal["en", "es"] = "en"


class ImageRequest(BaseModel):
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


async def get_session() -> AsyncSession:
    raise RuntimeError("Database session dependency was not configured.")


async def get_current_user() -> User:
    raise RuntimeError("Authentication dependency was not configured.")


async def get_storage() -> S3Storage:
    raise RuntimeError("Storage dependency was not configured.")


async def owned_scan(session: AsyncSession, user: User, scan_id: UUID) -> Scan:
    scan = await session.scalar(
        select(Scan).where(
            Scan.id == scan_id, Scan.tenant_id == user.tenant_id, Scan.user_id == user.id
        )
    )
    if scan is None:
        raise HTTPException(404, "Scan was not found.")
    return scan


@router.post("", response_model=CreateScanResponse, status_code=201)
async def create_scan(
    request: CreateScanRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> CreateScanResponse:
    scan = Scan(
        id=uuid4(),
        tenant_id=user.tenant_id,
        user_id=user.id,
        status="draft",
        requested_language=request.requested_language,
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
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> UploadInstruction:
    scan = await owned_scan(session, user, scan_id)
    if scan.status not in {"draft", "uploading"}:
        raise HTTPException(409, "Images cannot be added after analysis begins.")
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
    if completed + pending >= 8:
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
    scan.status = "uploading"
    await session.commit()
    return UploadInstruction(
        image_id=image.id, role=request.role, url=url, headers=headers, expires_at=expires
    )


@router.delete("/{scan_id}/images/{image_id}", status_code=200, response_class=Response)
async def remove_image(
    scan_id: UUID,
    image_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    storage: Annotated[S3Storage, Depends(get_storage)],
) -> None:
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
    try:
        storage.delete_object(image.object_key)
    except Exception:
        pass
    await session.delete(image)
    await session.commit()


class CompleteUploadRequest(BaseModel):
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
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AnalysisResponse:
    scan = await owned_scan(session, user, scan_id)
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
    scan.analysis_operation_key = key
    scan.status = "queued"
    scan.analysis_stage = "queued"
    await session.commit()
    from fabricassist.worker.celery_app import celery_app

    celery_app.send_task("fabricassist.analyse_scan", args=[str(scan.id)])
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
            RenderedAnswer.care_result_id == result.id, RenderedAnswer.language == language
        )
    )
    return ResultResponse(
        scan_id=scan.id,
        status=result.status,
        result=rendered.answer if rendered else result.canonical_data,
    )
