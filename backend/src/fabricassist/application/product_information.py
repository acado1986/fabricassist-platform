"""Product-information port, DTOs, and durable application orchestration."""
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.domain.products import ProductMatchStatus
from fabricassist.infrastructure.persistence.models import (
    ProductIdentifier,
    ProductLookupRun,
    ProductProfile,
    Scan,
)


@dataclass(frozen=True)
class ProductLookupResult:
    status: ProductMatchStatus
    provider: str
    source_name: str | None = None
    source_reference: str | None = None
    license_name: str | None = None
    product: dict[str, object] | None = None


class CatalogProduct(BaseModel):
    """Small, typed catalog boundary; untrusted catalog fields are not retained."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    brand: Annotated[str, StringConstraints(max_length=160)] | None = None
    name: Annotated[str, StringConstraints(max_length=240)] | None = None
    variant: Annotated[str, StringConstraints(max_length=160)] | None = None
    materials: list[Annotated[str, StringConstraints(max_length=80)]] = Field(
        default_factory=list, max_length=20
    )


class ProductInformationProvider(Protocol):
    async def lookup(self, barcode: str) -> ProductLookupResult: ...


class ProductInformationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RetryableProductInformationError(ProductInformationError):
    """A temporary enrichment failure; photographed analysis may continue."""


class PermanentProductInformationError(ProductInformationError):
    """A rejected or invalid enrichment request that must not be blind-retried."""


@dataclass(frozen=True)
class PersistedProductLookup:
    barcode: str
    status: str
    provider: str
    source_name: str | None
    source_reference: str | None
    license_name: str | None
    retrieved_at: datetime | None
    product: dict[str, object] | None


async def lookup_and_record(
    *,
    session: AsyncSession,
    scan: Scan,
    barcode: str,
    provider: ProductInformationProvider,
    cache_minutes: int = 1_440,
) -> PersistedProductLookup:
    """Lookup a validated barcode and persist provenance without identity linking."""
    fingerprint = hashlib.sha256(f"{provider.__class__.__name__}:{barcode}".encode()).hexdigest()
    cache_after = datetime.now(UTC) - timedelta(minutes=cache_minutes)
    cached = await session.scalar(
        select(ProductLookupRun)
        .where(
            ProductLookupRun.tenant_id == scan.tenant_id,
            ProductLookupRun.barcode == barcode,
            ProductLookupRun.request_fingerprint == fingerprint,
            ProductLookupRun.schema_version == "product-lookup-v1",
            ProductLookupRun.invalidated_at.is_(None),
            ProductLookupRun.created_at >= cache_after,
        )
        .order_by(ProductLookupRun.created_at.desc())
    )
    if cached is not None:
        cached.refreshed_at = datetime.now(UTC)
        return product_lookup_from_run(cached)
    result = await provider.lookup(barcode)
    profile: ProductProfile | None = None
    if result.product is not None:
        profile = await session.scalar(
            select(ProductProfile)
            .join(ProductIdentifier)
            .where(
                ProductProfile.tenant_id == scan.tenant_id,
                ProductIdentifier.normalized_value == barcode,
                ProductProfile.provider == result.provider,
                ProductProfile.invalidated_at.is_(None),
            )
        )
        if profile is None:
            profile = ProductProfile(
                id=uuid4(),
                tenant_id=scan.tenant_id,
                provider=result.provider,
                source_name=result.source_name or "Unknown",
                source_reference=result.source_reference,
                license_name=result.license_name,
                variant_data=result.product,
            )
            session.add(profile)
            await session.flush()
            session.add(
                ProductIdentifier(
                    id=uuid4(),
                    tenant_id=scan.tenant_id,
                    product_profile_id=profile.id,
                    identifier_type="barcode",
                    normalized_value=barcode,
                )
            )
    run = ProductLookupRun(
        id=uuid4(),
        tenant_id=scan.tenant_id,
        scan_id=scan.id,
        barcode=barcode,
        provider=result.provider,
        status=result.status.value,
        request_fingerprint=fingerprint,
        schema_version="product-lookup-v1",
        product_profile_id=profile.id if profile else None,
        safe_snapshot={
            "source_name": result.source_name,
            "source_reference": result.source_reference,
            "license_name": result.license_name,
            "product": result.product,
        },
        validated_snapshot=result.product or {},
    )
    session.add(run)
    await session.flush()
    return PersistedProductLookup(
        barcode=barcode,
        status=result.status.value,
        provider=result.provider,
        source_name=result.source_name,
        source_reference=result.source_reference,
        license_name=result.license_name,
        retrieved_at=run.created_at,
        product=result.product,
    )


def product_lookup_from_run(run: ProductLookupRun) -> PersistedProductLookup:
    snapshot = run.safe_snapshot
    return PersistedProductLookup(
        barcode=run.barcode,
        status=run.status,
        provider=run.provider,
        source_name=snapshot.get("source_name")
        if isinstance(snapshot.get("source_name"), str)
        else None,
        source_reference=(
            snapshot.get("source_reference")
            if isinstance(snapshot.get("source_reference"), str)
            else None
        ),
        license_name=snapshot.get("license_name")
        if isinstance(snapshot.get("license_name"), str)
        else None,
        retrieved_at=run.created_at,
        product=snapshot.get("product") if isinstance(snapshot.get("product"), dict) else None,
    )


async def invalidate_product_lookup(
    *, session: AsyncSession, scan: Scan, reason: str
) -> PersistedProductLookup | None:
    """Invalidate only the caller's scan lookup; product profiles stay generic.

    This deliberately does not delete a shared catalog profile or attach a
    barcode to a physical garment. A later lookup can refresh it safely.
    """
    run = await session.scalar(
        select(ProductLookupRun)
        .where(ProductLookupRun.scan_id == scan.id, ProductLookupRun.tenant_id == scan.tenant_id)
        .order_by(ProductLookupRun.created_at.desc())
    )
    if run is None:
        return None
    run.invalidated_at = datetime.now(UTC)
    run.invalidation_reason = reason
    return product_lookup_from_run(run)
