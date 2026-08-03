"""Transport-neutral query contracts for the unified v1 storefront reads."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from fabricassist.application.garment_analysis_cursor import GarmentAnalysisCursor
from fabricassist.application.garment_history_cursor import GarmentHistoryCursor
from fabricassist.application.storefront_cursors import (
    GarmentCursor,
    MessageCursor,
    ScanCursor,
)


@dataclass(frozen=True)
class StorefrontPrincipal:
    """The authenticated identity needed by tenant-scoped read ports."""

    user_id: UUID
    tenant_id: UUID
    email: str
    role: str
    preferred_language: str


@dataclass(frozen=True)
class ScanView:
    id: UUID
    status: str
    requested_language: str
    progress_percent: int
    analysis_stage: str | None
    error_code: str | None
    garment_id: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class GarmentView:
    id: UUID
    display_name: str | None
    archived_at: datetime | None
    active_result_id: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class GarmentHistoryView:
    id: UUID
    identifiers: list[str]
    thumbnail_url: str | None
    thumbnail_scan_id: UUID | None
    thumbnail_image_id: UUID | None
    last_analysis_at: datetime | None
    analysed_before: bool
    cleaned_before: bool
    service_events: list[ServiceEventView]


@dataclass(frozen=True)
class ServiceEventView:
    id: UUID
    kind: str
    note: str | None
    created_at: datetime


@dataclass(frozen=True)
class GarmentAnalysisHistoryView:
    scan_id: UUID
    status: str
    created_at: datetime
    result_available: bool
    thumbnail_scan_id: UUID | None
    thumbnail_image_id: UUID | None


@dataclass(frozen=True)
class GarmentObservationView:
    id: UUID
    observation_type: str
    stability: str
    value: dict[str, object]
    created_at: datetime


@dataclass(frozen=True)
class GarmentDetailView:
    id: UUID
    display_name: str | None
    identifiers: list[str]
    thumbnail_url: str | None
    thumbnail_scan_id: UUID | None
    thumbnail_image_id: UUID | None
    last_analysis_at: datetime | None
    analysed_before: bool
    cleaned_before: bool
    active_analysis: AnalysisRevisionView | None
    active_result: CareResultView | None
    analyses: list[GarmentAnalysisHistoryView]
    analyses_has_more: bool
    service_events: list[ServiceEventView]
    observations: list[GarmentObservationView]


@dataclass(frozen=True)
class ConversationMessageView:
    id: UUID
    role: str
    status: str
    text: str
    created_at: datetime


@dataclass(frozen=True)
class AnalysisRevisionView:
    id: UUID
    scan_id: UUID
    status: str
    revision_number: int
    created_at: datetime


@dataclass(frozen=True)
class RunView:
    id: UUID
    scan_id: UUID
    operation: str
    status: str
    error_code: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


@dataclass(frozen=True)
class ImageMetadataView:
    id: UUID
    role: str
    display_order: int
    width: int | None
    height: int | None
    viewpoint: str | None = None
    label_scope: str | None = None
    quality_state: str | None = None


@dataclass(frozen=True)
class UsageView:
    model_run_count: int
    estimated_cost_usd: Decimal


@dataclass(frozen=True)
class CareResultView:
    id: UUID
    status: str
    result: GarmentAnalysisResultView


@dataclass(frozen=True)
class EvidenceReferenceView:
    field_path: str
    source_kind: str
    certainty: str
    confidence: int
    source_image_ids: list[UUID]
    original_text: str | None
    uncertainty_reason: str | None


@dataclass(frozen=True)
class GarmentIssueView:
    id: UUID
    kind: str
    severity: str
    location: str
    observed_description: str
    confidence: int
    source_image_ids: list[UUID]
    suspected_causes: list[str]
    confirmed_cause: str | None
    cause_state: str


@dataclass(frozen=True)
class LabelTextView:
    image_id: UUID
    text: str
    language: str
    confidence: int


@dataclass(frozen=True)
class MaterialView:
    material: str
    percentage: float | None
    confidence: int
    source_image_ids: list[UUID]


@dataclass(frozen=True)
class CareActionView:
    code: str
    permission: str
    maximum_temperature_c: int | None
    process: str | None
    evidence_paths: list[str]
    reason_key: str
    professional_only: bool


@dataclass(frozen=True)
class ConflictView:
    id: UUID
    field_path: str
    selected_value: str | None
    resolution_code: str
    explanation_key: str
    severity: str


@dataclass(frozen=True)
class BranchSummaryView:
    branch: str
    status: str
    schema_version: str | None


@dataclass(frozen=True)
class StainStepView:
    claim_id: UUID
    status: str
    text: str | None
    action_code: str
    violation_codes: list[str]


@dataclass(frozen=True)
class VersionView:
    name: str
    value: str


@dataclass(frozen=True)
class GarmentAnalysisResultView:
    """Current, provider-free result projection for GraphQL and Expo clients."""

    schema_version: str
    outcome: str
    warnings: list[str]
    category: str
    subtype: str | None
    colors: list[str]
    pattern: str
    features: list[str]
    overall_condition: str
    issues: list[GarmentIssueView]
    visible_label_text: list[LabelTextView]
    materials: list[MaterialView]
    label_warnings: list[str]
    allowed_actions: list[CareActionView]
    prohibited_actions: list[CareActionView]
    unknown_actions: list[CareActionView]
    professional_only_actions: list[CareActionView]
    uncertainties: list[str]
    clearer_image_requests: list[str]
    conflicts: list[ConflictView]
    branches: list[BranchSummaryView]
    stain_steps: list[StainStepView]
    history_event_ids: list[UUID]
    preference_source: str
    versions: list[VersionView]


@dataclass(frozen=True)
class IdentityCandidateView:
    id: UUID
    garment_id: UUID
    thumbnail_scan_id: UUID | None
    thumbnail_image_id: UUID | None
    classification: str
    reasons: dict[str, object]
    status: str


@dataclass(frozen=True)
class ResultCompositeView:
    scan: ScanView
    active_analysis: AnalysisRevisionView | None
    result: CareResultView | None
    garment: GarmentView | None
    identity_candidates: list[IdentityCandidateView]


class StorefrontQueryPort(Protocol):
    """Queries shared by REST compatibility reads and GraphQL adapters."""

    async def list_scans(
        self, principal: StorefrontPrincipal, *, first: int, after: ScanCursor | None
    ) -> tuple[list[ScanView], bool]: ...

    async def get_scan(self, principal: StorefrontPrincipal, scan_id: UUID) -> ScanView | None: ...

    async def get_scans(
        self, principal: StorefrontPrincipal, scan_ids: Sequence[UUID]
    ) -> Mapping[UUID, ScanView]: ...

    async def list_garments(
        self, principal: StorefrontPrincipal, *, first: int, after: GarmentCursor | None
    ) -> tuple[list[GarmentView], bool]: ...

    async def get_garment(
        self, principal: StorefrontPrincipal, garment_id: UUID
    ) -> GarmentView | None: ...

    async def get_garments(
        self, principal: StorefrontPrincipal, garment_ids: Sequence[UUID]
    ) -> Mapping[UUID, GarmentView]: ...

    async def list_garment_history(
        self,
        principal: StorefrontPrincipal,
        *,
        first: int,
        after: GarmentHistoryCursor | None,
    ) -> tuple[list[GarmentHistoryView], bool]: ...

    async def get_garment_detail(
        self,
        principal: StorefrontPrincipal,
        garment_id: UUID,
        *,
        first: int,
        after: GarmentAnalysisCursor | None,
        language: str,
    ) -> GarmentDetailView | None: ...

    async def list_messages(
        self,
        principal: StorefrontPrincipal,
        *,
        scan_id: UUID,
        first: int,
        after: MessageCursor | None,
    ) -> tuple[list[ConversationMessageView], bool]: ...

    async def get_analysis_revision(
        self, principal: StorefrontPrincipal, revision_id: UUID
    ) -> AnalysisRevisionView | None: ...

    async def get_analysis_revisions(
        self, principal: StorefrontPrincipal, revision_ids: Sequence[UUID]
    ) -> Mapping[UUID, AnalysisRevisionView]: ...

    async def get_image_metadata(
        self, principal: StorefrontPrincipal, scan_id: UUID
    ) -> list[ImageMetadataView] | None: ...

    async def get_images_metadata(
        self, principal: StorefrontPrincipal, scan_ids: Sequence[UUID]
    ) -> Mapping[UUID, list[ImageMetadataView] | None]: ...

    async def get_run(self, principal: StorefrontPrincipal, run_id: UUID) -> RunView | None: ...

    async def get_runs(
        self, principal: StorefrontPrincipal, run_ids: Sequence[UUID]
    ) -> Mapping[UUID, RunView]: ...

    async def get_usage(self, principal: StorefrontPrincipal) -> UsageView | None: ...

    async def get_result_composite(
        self, principal: StorefrontPrincipal, scan_id: UUID, *, language: str
    ) -> ResultCompositeView | None: ...
