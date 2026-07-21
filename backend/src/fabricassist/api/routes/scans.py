"""Tenant-protected direct upload endpoints for Phase 7."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.infrastructure.persistence.models import Scan, ScanImage, User
from fabricassist.infrastructure.storage.s3 import S3Storage

router = APIRouter(prefix="/api/v1/scans", tags=["scans"])


class CreateScanRequest(BaseModel):
    kind: Literal["garment", "care_label", "other"]
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    requested_language: Literal["en", "es"] = "en"


class UploadInstruction(BaseModel):
    upload_id: UUID
    url: str
    headers: dict[str, str]
    expires_at: datetime


class CreateScanResponse(BaseModel):
    scan_id: UUID
    status: str
    upload: UploadInstruction


class CompleteUploadRequest(BaseModel):
    upload_id: UUID
    content_type: Literal["image/jpeg", "image/png", "image/webp"]


class ScanResponse(BaseModel):
    scan_id: UUID
    status: str
    images_completed: int


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
    image_id = uuid4()
    object_key = f"tenants/{user.tenant_id}/scans/{scan.id}/images/{image_id}"
    image = ScanImage(
        id=image_id,
        tenant_id=user.tenant_id,
        scan_id=scan.id,
        kind=request.kind,
        object_key=object_key,
        upload_expires_at=datetime.now(UTC),
    )
    session.add_all([scan, image])
    await session.flush()
    url, headers, expires_at = storage.presign_put(
        key=object_key, content_type=request.content_type
    )
    image.upload_expires_at = expires_at
    await session.commit()
    return CreateScanResponse(
        scan_id=scan.id,
        status=scan.status,
        upload=UploadInstruction(
            upload_id=image.upload_token, url=url, headers=headers, expires_at=expires_at
        ),
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
        select(ScanImage).where(ScanImage.scan_id == scan.id, ScanImage.completed_at.is_not(None))
    )
    return ScanResponse(
        scan_id=scan.id, status=scan.status, images_completed=1 if completed is not None else 0
    )
