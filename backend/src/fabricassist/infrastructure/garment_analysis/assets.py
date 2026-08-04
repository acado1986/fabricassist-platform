"""Private, revision-scoped provider-image loading for garment analysis."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fabricassist.application.garment_analysis import (
    AnalysisBranch,
    ProviderImage,
    normalize_image_bytes,
)
from fabricassist.application.object_storage import ObjectStorage
from fabricassist.domain.evidence import ImageRole
from fabricassist.domain.garment_analysis.image_routing import (
    AnalysisImage,
    ImageViewpoint,
    LabelScope,
    QualityState,
    route_images,
)
from fabricassist.infrastructure.persistence.models import RevisionImage, ScanImage


class SqlAlchemyRevisionImageAssets:
    """Read only revision-owned images and strip EXIF before provider submission."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        storage: ObjectStorage,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage

    async def branch_images(
        self, *, tenant_id: UUID, revision_id: UUID, branch: AnalysisBranch
    ) -> tuple[ProviderImage, ...]:
        async with self._session_factory() as session:
            rows = list(
                (
                    await session.scalars(
                        select(ScanImage)
                        .join(RevisionImage, RevisionImage.image_id == ScanImage.id)
                        .where(
                            RevisionImage.revision_id == revision_id,
                            RevisionImage.tenant_id == tenant_id,
                            ScanImage.tenant_id == tenant_id,
                            ScanImage.completed_at.is_not(None),
                            ScanImage.deleted_at.is_(None),
                        )
                        .order_by(ScanImage.display_order, ScanImage.created_at, ScanImage.id)
                    )
                ).all()
            )
        routed = route_images(
            tuple(
                AnalysisImage(
                    image_id=row.id,
                    role=ImageRole(row.role),
                    viewpoint=ImageViewpoint(row.viewpoint or "unknown"),
                    label_scope=LabelScope(row.label_scope or "unknown"),
                    quality_state=QualityState(row.quality_state or "unknown"),
                    blur_score=row.blur_score,
                    brightness_score=row.brightness_score,
                    contrast_score=row.contrast_score,
                    glare_score=row.glare_score,
                    crop_readability_score=row.crop_readability_score,
                    orientation_degrees=row.orientation_degrees,
                    display_order=row.display_order,
                )
                for row in rows
            )
        )
        selected = {
            AnalysisBranch.GARMENT_INSPECTION: routed.garment_inspection,
            AnalysisBranch.LABEL_EXTRACTION: routed.label_extraction,
            AnalysisBranch.BARCODE_ENRICHMENT: routed.barcode_enrichment,
            AnalysisBranch.STAIN_TREATMENT: routed.stain_treatment,
        }[branch]
        by_id = {row.id: row for row in rows}
        return tuple(
            ProviderImage(
                image_id=image_id,
                jpeg_bytes=normalize_image_bytes(
                    self._storage.read_object(by_id[image_id].object_key)
                ).jpeg_bytes,
                role=by_id[image_id].role,
                viewpoint=by_id[image_id].viewpoint or "unknown",
                label_scope=by_id[image_id].label_scope or "unknown",
                quality_state=by_id[image_id].quality_state or "unknown",
            )
            for image_id in selected
        )
