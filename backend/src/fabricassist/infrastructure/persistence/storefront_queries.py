"""SQLAlchemy adapter for the transport-neutral storefront query port."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from fabricassist.application.garment_analysis_cursor import GarmentAnalysisCursor
from fabricassist.application.garment_history_cursor import GarmentHistoryCursor
from fabricassist.application.object_storage import ObjectStorage
from fabricassist.application.storefront_cursors import GarmentCursor, MessageCursor, ScanCursor
from fabricassist.application.storefront_queries import (
    AnalysisRevisionView,
    CareResultView,
    ConversationMessageView,
    GarmentAnalysisHistoryView,
    GarmentDetailView,
    GarmentHistoryView,
    GarmentObservationView,
    GarmentView,
    IdentityCandidateView,
    ImageMetadataView,
    ResultCompositeView,
    RunView,
    ScanView,
    ServiceEventView,
    StorefrontPrincipal,
    StorefrontQueryPort,
    UsageView,
)
from fabricassist.domain.garment_analysis.models import FabricAssistAnalysisResult
from fabricassist.infrastructure.persistence.garment_analysis_projection import analysis_result_view
from fabricassist.infrastructure.persistence.models import (
    AiRun,
    AnalysisRevision,
    CareResult,
    ConversationMessage,
    ConversationThread,
    Garment,
    GarmentIdentifier,
    GarmentIdentityCandidate,
    GarmentIdentityMatchRun,
    GarmentObservation,
    GarmentServiceEvent,
    ModelRun,
    Scan,
    ScanImage,
)


class SqlAlchemyStorefrontQueries(StorefrontQueryPort):
    """Keep SQL, object-storage details, and ownership filters in infrastructure."""

    def __init__(self, session: AsyncSession, storage: ObjectStorage | None = None) -> None:
        self._session = session
        self._storage = storage

    async def list_scans(
        self, principal: StorefrontPrincipal, *, first: int, after: ScanCursor | None
    ) -> tuple[list[ScanView], bool]:
        statement = select(Scan).where(
            Scan.tenant_id == principal.tenant_id,
            Scan.user_id == principal.user_id,
            Scan.status != "deleted",
        )
        if after is not None:
            previous = await self._session.scalar(
                select(Scan).where(
                    Scan.id == after.scan_id,
                    Scan.tenant_id == principal.tenant_id,
                    Scan.user_id == principal.user_id,
                    Scan.status != "deleted",
                )
            )
            if previous is None:
                return [], False
            statement = statement.where(
                (Scan.created_at < previous.created_at)
                | ((Scan.created_at == previous.created_at) & (Scan.id < previous.id))
            )
        rows = list(
            (
                await self._session.scalars(
                    statement.order_by(Scan.created_at.desc(), Scan.id.desc()).limit(first + 1)
                )
            ).all()
        )
        has_more = len(rows) > first
        return [self._scan(row) for row in rows[:first]], has_more

    async def get_scan(self, principal: StorefrontPrincipal, scan_id: UUID) -> ScanView | None:
        row = await self._session.scalar(
            select(Scan).where(
                Scan.id == scan_id,
                Scan.tenant_id == principal.tenant_id,
                Scan.user_id == principal.user_id,
                Scan.status != "deleted",
            )
        )
        return self._scan(row) if row else None

    async def get_scans(
        self, principal: StorefrontPrincipal, scan_ids: Sequence[UUID]
    ) -> dict[UUID, ScanView]:
        if not scan_ids:
            return {}
        rows = list(
            (
                await self._session.scalars(
                    select(Scan).where(
                        Scan.id.in_(scan_ids),
                        Scan.tenant_id == principal.tenant_id,
                        Scan.user_id == principal.user_id,
                        Scan.status != "deleted",
                    )
                )
            ).all()
        )
        return {row.id: self._scan(row) for row in rows}

    async def list_garments(
        self, principal: StorefrontPrincipal, *, first: int, after: GarmentCursor | None
    ) -> tuple[list[GarmentView], bool]:
        statement = select(Garment).where(
            Garment.tenant_id == principal.tenant_id,
            Garment.user_id == principal.user_id,
            Garment.archived_at.is_(None),
        )
        if after is not None:
            previous = await self._session.scalar(
                select(Garment).where(
                    Garment.id == after.garment_id,
                    Garment.tenant_id == principal.tenant_id,
                    Garment.user_id == principal.user_id,
                    Garment.archived_at.is_(None),
                )
            )
            if previous is None:
                return [], False
            statement = statement.where(
                (Garment.created_at < previous.created_at)
                | ((Garment.created_at == previous.created_at) & (Garment.id < previous.id))
            )
        rows = list(
            (
                await self._session.scalars(
                    statement.order_by(Garment.created_at.desc(), Garment.id.desc()).limit(
                        first + 1
                    )
                )
            ).all()
        )
        has_more = len(rows) > first
        return [self._garment(row) for row in rows[:first]], has_more

    async def get_garment(
        self, principal: StorefrontPrincipal, garment_id: UUID
    ) -> GarmentView | None:
        row = await self._session.scalar(
            select(Garment).where(
                Garment.id == garment_id,
                Garment.tenant_id == principal.tenant_id,
                Garment.user_id == principal.user_id,
                Garment.archived_at.is_(None),
            )
        )
        return self._garment(row) if row else None

    async def get_garments(
        self, principal: StorefrontPrincipal, garment_ids: Sequence[UUID]
    ) -> dict[UUID, GarmentView]:
        if not garment_ids:
            return {}
        rows = list(
            (
                await self._session.scalars(
                    select(Garment).where(
                        Garment.id.in_(garment_ids),
                        Garment.tenant_id == principal.tenant_id,
                        Garment.user_id == principal.user_id,
                        Garment.archived_at.is_(None),
                    )
                )
            ).all()
        )
        return {row.id: self._garment(row) for row in rows}

    async def list_garment_history(
        self,
        principal: StorefrontPrincipal,
        *,
        first: int,
        after: GarmentHistoryCursor | None,
    ) -> tuple[list[GarmentHistoryView], bool]:
        revision = AnalysisRevision
        statement = (
            select(Garment, revision.created_at.label("last_analysis_at"))
            .outerjoin(
                revision,
                (revision.id == Garment.active_analysis_revision_id)
                & (revision.tenant_id == principal.tenant_id),
            )
            .where(
                Garment.tenant_id == principal.tenant_id,
                Garment.user_id == principal.user_id,
                Garment.archived_at.is_(None),
            )
        )
        if after:
            analysis_at = after.last_analysis_at
            if analysis_at is None:
                statement = statement.where(
                    revision.created_at.is_(None), Garment.id < after.garment_id
                )
            else:
                statement = statement.where(
                    or_(
                        revision.created_at < analysis_at,
                        revision.created_at.is_(None),
                        and_(revision.created_at == analysis_at, Garment.id < after.garment_id),
                    )
                )
        rows = list(
            (
                await self._session.execute(
                    statement.order_by(
                        revision.created_at.desc().nullslast(), Garment.id.desc()
                    ).limit(first + 1)
                )
            ).all()
        )
        has_more = len(rows) > first
        rows = rows[:first]
        garment_ids = [row[0].id for row in rows]
        if not garment_ids:
            return [], has_more

        identifiers = list(
            (
                await self._session.scalars(
                    select(GarmentIdentifier).where(
                        GarmentIdentifier.tenant_id == principal.tenant_id,
                        GarmentIdentifier.garment_id.in_(garment_ids),
                        GarmentIdentifier.verification_status == "verified",
                    )
                )
            ).all()
        )
        events = list(
            (
                await self._session.scalars(
                    select(GarmentServiceEvent).where(
                        GarmentServiceEvent.tenant_id == principal.tenant_id,
                        GarmentServiceEvent.garment_id.in_(garment_ids),
                    )
                )
            ).all()
        )
        image_rows = list(
            (
                await self._session.execute(
                    select(ScanImage, Scan.garment_id)
                    .join(Scan, Scan.id == ScanImage.scan_id)
                    .where(
                        Scan.tenant_id == principal.tenant_id,
                        Scan.user_id == principal.user_id,
                        Scan.garment_id.in_(garment_ids),
                        ScanImage.completed_at.is_not(None),
                        ScanImage.deleted_at.is_(None),
                    )
                    .order_by(ScanImage.created_at.desc(), ScanImage.id.desc())
                )
            ).all()
        )
        identifiers_by_garment: dict[UUID, list[str]] = {
            garment_id: [] for garment_id in garment_ids
        }
        for identifier in identifiers:
            identifiers_by_garment[identifier.garment_id].append(identifier.normalized_value)
        completed_by_garment = {garment_id: False for garment_id in garment_ids}
        for event in events:
            if event.kind == "completed":
                completed_by_garment[event.garment_id] = True
        thumbnail_by_garment: dict[UUID, tuple[ScanImage, UUID]] = {}
        for image, garment_id in image_rows:
            if garment_id is not None:
                thumbnail_by_garment.setdefault(garment_id, (image, image.scan_id))
        result: list[GarmentHistoryView] = []
        for garment, last_analysis_at in rows:
            thumbnail = thumbnail_by_garment.get(garment.id)
            result.append(
                GarmentHistoryView(
                    id=garment.id,
                    identifiers=identifiers_by_garment[garment.id],
                    thumbnail_url=(
                        self._storage.presign_get(key=thumbnail[0].object_key).url
                        if thumbnail is not None and self._storage is not None
                        else None
                    ),
                    thumbnail_scan_id=thumbnail[1] if thumbnail is not None else None,
                    thumbnail_image_id=thumbnail[0].id if thumbnail is not None else None,
                    last_analysis_at=last_analysis_at,
                    analysed_before=last_analysis_at is not None,
                    cleaned_before=completed_by_garment[garment.id],
                    service_events=[
                        ServiceEventView(
                            id=event.id,
                            kind=event.kind,
                            note=event.note,
                            created_at=event.created_at,
                        )
                        for event in events
                        if event.garment_id == garment.id
                    ],
                )
            )
        return result, has_more

    async def get_garment_detail(
        self,
        principal: StorefrontPrincipal,
        garment_id: UUID,
        *,
        first: int,
        after: GarmentAnalysisCursor | None,
        language: str,
    ) -> GarmentDetailView | None:
        garment = await self._session.scalar(
            select(Garment).where(
                Garment.id == garment_id,
                Garment.tenant_id == principal.tenant_id,
                Garment.user_id == principal.user_id,
                Garment.archived_at.is_(None),
            )
        )
        if garment is None:
            return None

        identifiers = list(
            (
                await self._session.scalars(
                    select(GarmentIdentifier.normalized_value).where(
                        GarmentIdentifier.tenant_id == principal.tenant_id,
                        GarmentIdentifier.garment_id == garment.id,
                        GarmentIdentifier.verification_status == "verified",
                    )
                )
            ).all()
        )
        events = list(
            (
                await self._session.scalars(
                    select(GarmentServiceEvent)
                    .where(
                        GarmentServiceEvent.tenant_id == principal.tenant_id,
                        GarmentServiceEvent.garment_id == garment.id,
                    )
                    .order_by(GarmentServiceEvent.created_at.desc(), GarmentServiceEvent.id.desc())
                )
            ).all()
        )
        statement = select(Scan).where(
            Scan.tenant_id == principal.tenant_id,
            Scan.user_id == principal.user_id,
            Scan.garment_id == garment.id,
            Scan.status != "deleted",
        )
        if after is not None:
            statement = statement.where(
                (Scan.created_at < after.created_at)
                | ((Scan.created_at == after.created_at) & (Scan.id < after.scan_id))
            )
        latest_scan = await self._session.scalar(
            select(Scan)
            .where(
                Scan.tenant_id == principal.tenant_id,
                Scan.user_id == principal.user_id,
                Scan.garment_id == garment.id,
                Scan.status != "deleted",
            )
            .order_by(Scan.created_at.desc(), Scan.id.desc())
        )
        scans = list(
            (
                await self._session.scalars(
                    statement.order_by(Scan.created_at.desc(), Scan.id.desc()).limit(first + 1)
                )
            ).all()
        )
        analyses_has_more = len(scans) > first
        scans = scans[:first]
        scan_ids = [scan.id for scan in scans]
        image_scan_ids = list(
            dict.fromkeys(scan_ids + ([latest_scan.id] if latest_scan is not None else []))
        )
        image_rows = (
            list(
                (
                    await self._session.scalars(
                        select(ScanImage)
                        .where(
                            ScanImage.tenant_id == principal.tenant_id,
                            ScanImage.scan_id.in_(image_scan_ids),
                            ScanImage.completed_at.is_not(None),
                            ScanImage.deleted_at.is_(None),
                        )
                        .order_by(ScanImage.created_at.desc(), ScanImage.id.desc())
                    )
                ).all()
            )
            if scan_ids
            else []
        )
        thumbnail_by_scan: dict[UUID, ScanImage] = {}
        for image in image_rows:
            thumbnail_by_scan.setdefault(image.scan_id, image)

        active_analysis = None
        if garment.active_analysis_revision_id is not None:
            revision = await self._session.scalar(
                select(AnalysisRevision).where(
                    AnalysisRevision.id == garment.active_analysis_revision_id,
                    AnalysisRevision.tenant_id == principal.tenant_id,
                    AnalysisRevision.garment_id == garment.id,
                )
            )
            if revision is not None:
                active_analysis = self._revision(revision)

        active_result = await self._rendered_result(
            principal,
            garment.active_result_id,
            language=language,
            analysis_revision_id=garment.active_analysis_revision_id,
        )
        latest_thumbnail = thumbnail_by_scan.get(latest_scan.id) if latest_scan else None
        superseding_observation = aliased(GarmentObservation)
        observations = list(
            (
                await self._session.scalars(
                    select(GarmentObservation)
                    .where(
                        GarmentObservation.tenant_id == principal.tenant_id,
                        GarmentObservation.garment_id == garment.id,
                        ~select(superseding_observation.id)
                        .where(
                            superseding_observation.supersedes_observation_id
                            == GarmentObservation.id
                        )
                        .exists(),
                    )
                    .order_by(GarmentObservation.created_at.desc(), GarmentObservation.id.desc())
                )
            ).all()
        )
        return GarmentDetailView(
            id=garment.id,
            display_name=garment.display_name,
            identifiers=list(identifiers),
            thumbnail_url=(
                self._storage.presign_get(key=latest_thumbnail.object_key).url
                if latest_thumbnail is not None and self._storage is not None
                else None
            ),
            thumbnail_scan_id=(latest_thumbnail.scan_id if latest_thumbnail is not None else None),
            thumbnail_image_id=(latest_thumbnail.id if latest_thumbnail is not None else None),
            last_analysis_at=(latest_scan.created_at if latest_scan is not None else None),
            analysed_before=garment.active_analysis_revision_id is not None,
            cleaned_before=any(event.kind == "completed" for event in events),
            active_analysis=active_analysis,
            active_result=active_result,
            analyses=[
                GarmentAnalysisHistoryView(
                    scan_id=scan.id,
                    status=scan.status,
                    created_at=scan.created_at,
                    result_available=scan.active_result_id is not None,
                    thumbnail_scan_id=(
                        thumbnail_by_scan[scan.id].scan_id if scan.id in thumbnail_by_scan else None
                    ),
                    thumbnail_image_id=(
                        thumbnail_by_scan[scan.id].id if scan.id in thumbnail_by_scan else None
                    ),
                )
                for scan in scans
            ],
            analyses_has_more=analyses_has_more,
            service_events=[
                ServiceEventView(
                    id=event.id,
                    kind=event.kind,
                    note=event.note,
                    created_at=event.created_at,
                )
                for event in events
            ],
            observations=[
                GarmentObservationView(
                    id=observation.id,
                    observation_type=observation.observation_type,
                    stability=observation.stability,
                    authority=observation.authority,
                    value=cast(dict[str, object], observation.value),
                    evidence_ids=[UUID(value) for value in observation.evidence_ids],
                    confidence=observation.confidence,
                    analysis_revision_id=observation.analysis_revision_id,
                    supersedes_observation_id=observation.supersedes_observation_id,
                    created_at=observation.created_at,
                )
                for observation in observations
            ],
        )

    async def list_messages(
        self,
        principal: StorefrontPrincipal,
        *,
        scan_id: UUID,
        first: int,
        after: MessageCursor | None,
    ) -> tuple[list[ConversationMessageView], bool]:
        scan = await self._session.scalar(
            select(Scan).where(
                Scan.id == scan_id,
                Scan.tenant_id == principal.tenant_id,
                Scan.user_id == principal.user_id,
                Scan.status != "deleted",
            )
        )
        if scan is None or scan.garment_id is None:
            return [], False
        thread = await self._session.scalar(
            select(ConversationThread).where(
                ConversationThread.tenant_id == principal.tenant_id,
                ConversationThread.garment_id == scan.garment_id,
                ConversationThread.user_id == principal.user_id,
            )
        )
        if thread is None:
            return [], False
        statement = select(ConversationMessage).where(ConversationMessage.thread_id == thread.id)
        if after is not None:
            previous = await self._session.scalar(
                select(ConversationMessage).where(
                    ConversationMessage.id == after.message_id,
                    ConversationMessage.thread_id == thread.id,
                )
            )
            if previous is None:
                return [], False
            statement = statement.where(
                (ConversationMessage.created_at > previous.created_at)
                | (
                    (ConversationMessage.created_at == previous.created_at)
                    & (ConversationMessage.id > previous.id)
                )
            )
        rows = list(
            (
                await self._session.scalars(
                    statement.order_by(
                        ConversationMessage.created_at, ConversationMessage.id
                    ).limit(first + 1)
                )
            ).all()
        )
        has_more = len(rows) > first
        return [self._message(row) for row in rows[:first]], has_more

    async def get_analysis_revision(
        self, principal: StorefrontPrincipal, revision_id: UUID
    ) -> AnalysisRevisionView | None:
        row = await self._session.scalar(
            select(AnalysisRevision)
            .join(Scan, Scan.id == AnalysisRevision.scan_id)
            .where(
                AnalysisRevision.id == revision_id,
                AnalysisRevision.tenant_id == principal.tenant_id,
                Scan.user_id == principal.user_id,
            )
        )
        return self._revision(row) if row else None

    async def get_analysis_revisions(
        self, principal: StorefrontPrincipal, revision_ids: Sequence[UUID]
    ) -> dict[UUID, AnalysisRevisionView]:
        if not revision_ids:
            return {}
        rows = list(
            (
                await self._session.scalars(
                    select(AnalysisRevision)
                    .join(Scan, Scan.id == AnalysisRevision.scan_id)
                    .where(
                        AnalysisRevision.id.in_(revision_ids),
                        AnalysisRevision.tenant_id == principal.tenant_id,
                        Scan.user_id == principal.user_id,
                    )
                )
            ).all()
        )
        return {row.id: self._revision(row) for row in rows}

    async def get_image_metadata(
        self, principal: StorefrontPrincipal, scan_id: UUID
    ) -> list[ImageMetadataView] | None:
        scan = await self._session.scalar(
            select(Scan).where(
                Scan.id == scan_id,
                Scan.tenant_id == principal.tenant_id,
                Scan.user_id == principal.user_id,
                Scan.status != "deleted",
            )
        )
        if scan is None:
            return None
        rows = list(
            (
                await self._session.scalars(
                    select(ScanImage)
                    .where(
                        ScanImage.scan_id == scan.id,
                        ScanImage.tenant_id == principal.tenant_id,
                        ScanImage.completed_at.is_not(None),
                        ScanImage.deleted_at.is_(None),
                    )
                    .order_by(ScanImage.display_order, ScanImage.created_at)
                )
            ).all()
        )
        return [
            ImageMetadataView(
                id=row.id,
                role=row.role,
                viewpoint=row.viewpoint,
                label_scope=row.label_scope,
                quality_state=row.quality_state,
                display_order=row.display_order,
                width=row.width,
                height=row.height,
            )
            for row in rows
        ]

    async def get_images_metadata(
        self, principal: StorefrontPrincipal, scan_ids: Sequence[UUID]
    ) -> dict[UUID, list[ImageMetadataView] | None]:
        if not scan_ids:
            return {}
        scans = list(
            (
                await self._session.scalars(
                    select(Scan).where(
                        Scan.id.in_(scan_ids),
                        Scan.tenant_id == principal.tenant_id,
                        Scan.user_id == principal.user_id,
                        Scan.status != "deleted",
                    )
                )
            ).all()
        )
        result: dict[UUID, list[ImageMetadataView] | None] = {scan.id: [] for scan in scans}
        if not scans:
            return result
        rows = list(
            (
                await self._session.scalars(
                    select(ScanImage)
                    .where(
                        ScanImage.scan_id.in_([scan.id for scan in scans]),
                        ScanImage.tenant_id == principal.tenant_id,
                        ScanImage.completed_at.is_not(None),
                        ScanImage.deleted_at.is_(None),
                    )
                    .order_by(ScanImage.display_order, ScanImage.created_at)
                )
            ).all()
        )
        for row in rows:
            metadata = result[row.scan_id]
            if metadata is not None:
                metadata.append(
                    ImageMetadataView(
                        id=row.id,
                        role=row.role,
                        viewpoint=row.viewpoint,
                        label_scope=row.label_scope,
                        quality_state=row.quality_state,
                        display_order=row.display_order,
                        width=row.width,
                        height=row.height,
                    )
                )
        return result

    async def get_run(self, principal: StorefrontPrincipal, run_id: UUID) -> RunView | None:
        row = await self._session.scalar(
            select(AiRun).where(
                AiRun.id == run_id,
                AiRun.tenant_id == principal.tenant_id,
                AiRun.user_id == principal.user_id,
            )
        )
        return self._run(row) if row else None

    async def get_runs(
        self, principal: StorefrontPrincipal, run_ids: Sequence[UUID]
    ) -> dict[UUID, RunView]:
        if not run_ids:
            return {}
        rows = list(
            (
                await self._session.scalars(
                    select(AiRun).where(
                        AiRun.id.in_(run_ids),
                        AiRun.tenant_id == principal.tenant_id,
                        AiRun.user_id == principal.user_id,
                    )
                )
            ).all()
        )
        return {row.id: self._run(row) for row in rows}

    async def get_usage(self, principal: StorefrontPrincipal) -> UsageView | None:
        if principal.role != "admin":
            return None
        result = await self._session.execute(
            select(
                func.count(ModelRun.id), func.coalesce(func.sum(ModelRun.estimated_cost_usd), 0)
            ).where(ModelRun.tenant_id == principal.tenant_id)
        )
        count, cost = cast(tuple[int, Decimal | None], result.one())
        return UsageView(model_run_count=count, estimated_cost_usd=cost or Decimal(0))

    async def _rendered_result(
        self,
        principal: StorefrontPrincipal,
        result_id: UUID | None,
        *,
        language: str,
        analysis_revision_id: UUID | None,
    ) -> CareResultView | None:
        if result_id is None or analysis_revision_id is None:
            return None
        result_row = await self._session.scalar(
            select(CareResult).where(
                CareResult.id == result_id,
                CareResult.tenant_id == principal.tenant_id,
                CareResult.analysis_revision_id == analysis_revision_id,
            )
        )
        if result_row is None:
            return None
        # Phase 9 deliberately reads only the versioned v2 canonical projection.
        # Old rendered JSON is not a transport fallback; Phase 10 transforms retained
        # results before enabling this feature for production traffic.
        payload = result_row.canonical_data.get("garment_analysis_result")
        if not isinstance(payload, dict):
            return None
        try:
            canonical = FabricAssistAnalysisResult.model_validate(payload)
        except ValueError:
            return None
        return CareResultView(
            id=result_row.id,
            status=result_row.status,
            result=analysis_result_view(canonical),
        )

    async def get_result_composite(
        self, principal: StorefrontPrincipal, scan_id: UUID, *, language: str
    ) -> ResultCompositeView | None:
        scan = await self._session.scalar(
            select(Scan).where(
                Scan.id == scan_id,
                Scan.tenant_id == principal.tenant_id,
                Scan.user_id == principal.user_id,
                Scan.status != "deleted",
            )
        )
        if scan is None:
            return None

        active_analysis = None
        if scan.active_analysis_revision_id is not None:
            revision = await self._session.scalar(
                select(AnalysisRevision).where(
                    AnalysisRevision.id == scan.active_analysis_revision_id,
                    AnalysisRevision.tenant_id == principal.tenant_id,
                    AnalysisRevision.scan_id == scan.id,
                )
            )
            if revision is not None:
                active_analysis = self._revision(revision)

        result_view = await self._rendered_result(
            principal,
            scan.active_result_id,
            language=language,
            analysis_revision_id=scan.active_analysis_revision_id,
        )

        garment = None
        if scan.garment_id is not None:
            garment_row = await self._session.scalar(
                select(Garment).where(
                    Garment.id == scan.garment_id,
                    Garment.tenant_id == principal.tenant_id,
                    Garment.user_id == principal.user_id,
                    Garment.archived_at.is_(None),
                )
            )
            if garment_row is not None:
                garment = self._garment(garment_row)

        candidates = list(
            (
                await self._session.scalars(
                    select(GarmentIdentityCandidate)
                    .join(
                        GarmentIdentityMatchRun,
                        GarmentIdentityMatchRun.id == GarmentIdentityCandidate.match_run_id,
                    )
                    .join(Garment, Garment.id == GarmentIdentityCandidate.garment_id)
                    .where(
                        GarmentIdentityCandidate.tenant_id == principal.tenant_id,
                        GarmentIdentityCandidate.status == "pending",
                        GarmentIdentityMatchRun.tenant_id == principal.tenant_id,
                        GarmentIdentityMatchRun.scan_id == scan.id,
                        Garment.tenant_id == principal.tenant_id,
                        Garment.user_id == principal.user_id,
                        Garment.archived_at.is_(None),
                    )
                )
            ).all()
        )
        candidate_thumbnail_by_garment: dict[UUID, ScanImage] = {}
        candidate_garment_ids = list({candidate.garment_id for candidate in candidates})
        if candidate_garment_ids:
            candidate_images = list(
                (
                    await self._session.execute(
                        select(ScanImage)
                        .add_columns(Scan.garment_id)
                        .join(Scan, Scan.id == ScanImage.scan_id)
                        .where(
                            ScanImage.tenant_id == principal.tenant_id,
                            ScanImage.completed_at.is_not(None),
                            ScanImage.deleted_at.is_(None),
                            Scan.tenant_id == principal.tenant_id,
                            Scan.user_id == principal.user_id,
                            Scan.garment_id.in_(candidate_garment_ids),
                            Scan.status != "deleted",
                        )
                        .order_by(
                            (ScanImage.role == "garment_overview").desc(),
                            Scan.created_at.desc(),
                            ScanImage.display_order.asc(),
                            ScanImage.created_at.desc(),
                            ScanImage.id.desc(),
                        )
                    )
                ).all()
            )
            for image, garment_id in candidate_images:
                candidate_thumbnail_by_garment.setdefault(garment_id, image)
        identity_candidate_views: list[IdentityCandidateView] = []
        for candidate in candidates:
            thumbnail = candidate_thumbnail_by_garment.get(candidate.garment_id)
            identity_candidate_views.append(
                IdentityCandidateView(
                    id=candidate.id,
                    garment_id=candidate.garment_id,
                    thumbnail_scan_id=thumbnail.scan_id if thumbnail is not None else None,
                    thumbnail_image_id=thumbnail.id if thumbnail is not None else None,
                    classification=candidate.classification,
                    reasons=cast(dict[str, object], candidate.reasons),
                    status=candidate.status,
                )
            )
        return ResultCompositeView(
            scan=self._scan(scan),
            active_analysis=active_analysis,
            result=result_view,
            garment=garment,
            identity_candidates=identity_candidate_views,
        )

    @staticmethod
    def _scan(row: Scan) -> ScanView:
        return ScanView(
            id=row.id,
            status=row.status,
            requested_language=row.requested_language,
            progress_percent=row.progress_percent,
            analysis_stage=row.analysis_stage,
            error_code=row.analysis_error_code,
            garment_id=row.garment_id,
            created_at=row.created_at,
        )

    @staticmethod
    def _garment(row: Garment) -> GarmentView:
        return GarmentView(
            id=row.id,
            display_name=row.display_name,
            archived_at=row.archived_at,
            active_result_id=row.active_result_id,
            created_at=row.created_at,
        )

    @staticmethod
    def _message(row: ConversationMessage) -> ConversationMessageView:
        return ConversationMessageView(
            id=row.id, role=row.role, status=row.status, text=row.text, created_at=row.created_at
        )

    @staticmethod
    def _revision(row: AnalysisRevision) -> AnalysisRevisionView:
        return AnalysisRevisionView(
            id=row.id,
            scan_id=row.scan_id,
            status=row.status,
            revision_number=row.revision_number,
            created_at=row.created_at,
        )

    @staticmethod
    def _run(row: AiRun) -> RunView:
        return RunView(
            id=row.id,
            scan_id=row.scan_id,
            operation=row.operation,
            status=row.status,
            error_code=row.error_code,
            created_at=row.created_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
        )
