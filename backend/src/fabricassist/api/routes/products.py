"""Tenant-scoped deterministic trusted product lookup API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.products import (
    get_product_provider,
    invalidate_product_lookup,
    lookup_and_record,
    product_lookup_from_run,
)
from fabricassist.domain.products import ProductLookupError, normalize_barcode
from fabricassist.infrastructure.persistence.models import (
    ProductLookupRun,
    Scan,
    User,
)
from fabricassist.settings import Settings

router = APIRouter(prefix="/api/v1/scans", tags=["products"])


class LookupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    barcode: str


class LookupResponse(BaseModel):
    barcode: str
    status: str
    provider: str
    source_name: str | None
    source_reference: str | None
    license_name: str | None
    retrieved_at: str | None = None
    product: dict[str, object] | None


class InvalidateLookupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str


async def get_session() -> AsyncSession:
    raise RuntimeError("Database session dependency was not configured.")


async def get_current_user() -> User:
    raise RuntimeError("Authentication dependency was not configured.")


async def get_settings() -> Settings:
    raise RuntimeError("Settings dependency was not configured.")


@router.post("/{scan_id}/product-lookup", response_model=LookupResponse)
async def product_lookup(
    scan_id: UUID,
    request: LookupRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LookupResponse:
    scan = await session.scalar(
        select(Scan).where(
            Scan.id == scan_id, Scan.tenant_id == user.tenant_id, Scan.user_id == user.id
        )
    )
    if scan is None:
        raise HTTPException(404, "Scan was not found.")
    try:
        barcode = normalize_barcode(request.barcode)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    try:
        lookup = await lookup_and_record(
            session=session,
            scan=scan,
            barcode=barcode,
            provider=get_product_provider(settings),
            cache_minutes=settings.product_cache_minutes,
        )
    except ProductLookupError as error:
        raise HTTPException(502, error.code) from error
    await session.commit()
    return LookupResponse(
        barcode=lookup.barcode,
        status=lookup.status,
        provider=lookup.provider,
        source_name=lookup.source_name,
        source_reference=lookup.source_reference,
        license_name=lookup.license_name,
        retrieved_at=lookup.retrieved_at.isoformat() if lookup.retrieved_at else None,
        product=lookup.product,
    )


@router.post("/{scan_id}/product-lookup/invalidate", status_code=200, response_class=Response)
async def invalidate_latest_product_lookup(
    scan_id: UUID,
    request: InvalidateLookupRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    scan = await session.scalar(
        select(Scan).where(
            Scan.id == scan_id, Scan.tenant_id == user.tenant_id, Scan.user_id == user.id
        )
    )
    if scan is None:
        raise HTTPException(404, "Scan was not found.")
    if not request.reason.strip() or len(request.reason) > 100:
        raise HTTPException(422, "INVALID_INVALIDATION_REASON")
    lookup = await invalidate_product_lookup(session=session, scan=scan, reason=request.reason)
    if lookup is None:
        raise HTTPException(404, "Product lookup was not found.")
    await session.commit()


@router.get("/{scan_id}/product-lookup", response_model=LookupResponse | None)
async def latest_product_lookup(
    scan_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> LookupResponse | None:
    run = await session.scalar(
        select(ProductLookupRun)
        .join(Scan)
        .where(
            ProductLookupRun.scan_id == scan_id,
            ProductLookupRun.tenant_id == user.tenant_id,
            Scan.user_id == user.id,
        )
        .order_by(ProductLookupRun.created_at.desc())
    )
    if run is None:
        return None
    lookup = product_lookup_from_run(run)
    return LookupResponse(
        barcode=lookup.barcode,
        status=lookup.status,
        provider=lookup.provider,
        source_name=lookup.source_name,
        source_reference=lookup.source_reference,
        license_name=lookup.license_name,
        retrieved_at=lookup.retrieved_at.isoformat() if lookup.retrieved_at else None,
        product=lookup.product,
    )
