"""Read-only Strawberry schema for canonical authenticated FabricAssist reads."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, cast
from uuid import UUID

import strawberry
from graphql import GraphQLError
from starlette.requests import Request
from strawberry.extensions import (
    DisableIntrospection,
    MaxAliasesLimiter,
    MaxTokensLimiter,
    QueryDepthLimiter,
)
from strawberry.extensions.base_extension import SchemaExtension
from strawberry.fastapi import BaseContext, GraphQLRouter
from strawberry.http import GraphQLHTTPResponse
from strawberry.scalars import JSON
from strawberry.types.execution import ExecutionResult

from fabricassist.api.graphql_loaders import GraphQLLoaders
from fabricassist.application.garment_analysis_cursor import (
    GarmentAnalysisCursor,
    decode_analysis_cursor,
    encode_analysis_cursor,
)
from fabricassist.application.garment_history_cursor import (
    GarmentHistoryCursor,
    decode_history_cursor,
    encode_history_cursor,
)
from fabricassist.application.storefront_cursors import (
    GarmentCursor,
    MessageCursor,
    ScanCursor,
    decode_garment_cursor,
    decode_message_cursor,
    decode_scan_cursor,
    encode_garment_cursor,
    encode_message_cursor,
    encode_scan_cursor,
)
from fabricassist.application.storefront_queries import (
    AnalysisRevisionView,
    CareResultView,
    ConversationMessageView,
    GarmentAnalysisHistoryView,
    GarmentDetailView,
    GarmentHistoryView,
    GarmentView,
    IdentityCandidateView,
    ImageMetadataView,
    ResultCompositeView,
    RunView,
    ScanView,
    ServiceEventView,
    StorefrontPrincipal,
    StorefrontQueryPort,
)
from fabricassist.settings import Settings


@strawberry.type
class PageInfo:
    next_cursor: str | None


@strawberry.type
class CurrentUserType:
    id: UUID
    email: str
    role: str
    preferred_language: str


@strawberry.type
class ScanImageMetadataType:
    id: UUID
    role: str
    display_order: int
    width: int | None
    height: int | None


@strawberry.type
class ScanType:
    id: UUID
    status: str
    requested_language: str
    progress_percent: int
    analysis_stage: str | None
    error_code: str | None
    garment_id: UUID | None
    created_at: datetime


@strawberry.type
class ScanConnection:
    items: list[ScanType]
    page_info: PageInfo


@strawberry.type
class GarmentType:
    id: UUID
    display_name: str | None
    archived_at: datetime | None
    active_result_id: UUID | None
    created_at: datetime


@strawberry.type
class GarmentConnection:
    items: list[GarmentType]
    page_info: PageInfo


@strawberry.type
class GarmentHistoryItemType:
    id: UUID
    identifiers: list[str]
    thumbnail_url: str | None
    thumbnail_scan_id: UUID | None
    thumbnail_image_id: UUID | None
    last_analysis_at: datetime | None
    analysed_before: bool
    cleaned_before: bool


@strawberry.type
class GarmentHistoryConnection:
    items: list[GarmentHistoryItemType]
    page_info: PageInfo


@strawberry.type
class ServiceEventType:
    id: UUID
    kind: str
    note: str | None
    created_at: datetime


@strawberry.type
class GarmentAnalysisHistoryType:
    scan_id: UUID
    status: str
    created_at: datetime
    result_available: bool
    thumbnail_scan_id: UUID | None
    thumbnail_image_id: UUID | None


@strawberry.type
class GarmentAnalysisHistoryConnection:
    items: list[GarmentAnalysisHistoryType]
    page_info: PageInfo


@strawberry.type
class GarmentDetailType:
    id: UUID
    display_name: str | None
    identifiers: list[str]
    thumbnail_scan_id: UUID | None
    thumbnail_image_id: UUID | None
    last_analysis_at: datetime | None
    analysed_before: bool
    cleaned_before: bool
    active_analysis: AnalysisRevisionType | None
    active_result: CareResultType | None
    analyses: GarmentAnalysisHistoryConnection
    service_events: list[ServiceEventType]


@strawberry.type
class ConversationMessageType:
    id: UUID
    role: str
    status: str
    text: str
    created_at: datetime


@strawberry.type
class ConversationMessageConnection:
    items: list[ConversationMessageType]
    page_info: PageInfo


@strawberry.type
class AnalysisRevisionType:
    id: UUID
    scan_id: UUID
    status: str
    revision_number: int
    created_at: datetime


@strawberry.type
class AiRunType:
    id: UUID
    scan_id: UUID
    operation: str
    status: str
    error_code: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


@strawberry.type
class UsageSummary:
    model_run_count: int
    estimated_cost_usd: str


@strawberry.type
class CareResultType:
    id: UUID
    status: str
    language: str
    data: JSON


@strawberry.type
class IdentityCandidateType:
    id: UUID
    garment_id: UUID
    thumbnail_scan_id: UUID | None
    thumbnail_image_id: UUID | None
    classification: str
    reasons: JSON
    status: str


@strawberry.type
class ResultCompositeType:
    scan: ScanType
    active_analysis: AnalysisRevisionType | None
    result: CareResultType | None
    garment: GarmentType | None
    identity_candidates: list[IdentityCandidateType]


class GraphQLContext(BaseContext):
    """Safe transport context; persistence sessions never reach resolvers."""

    def __init__(
        self,
        *,
        principal: StorefrontPrincipal,
        correlation_id: str,
        queries: StorefrontQueryPort,
        loaders: GraphQLLoaders,
    ) -> None:
        self.principal = principal
        self.correlation_id = correlation_id
        self.queries = queries
        self.loaders = loaders


class FabricAssistGraphQLRouter(GraphQLRouter):
    """Keep GraphQL error details deliberately smaller than internal failures."""

    async def process_result(
        self, request: Request, result: ExecutionResult
    ) -> GraphQLHTTPResponse:
        payload = await super().process_result(request, result)
        errors = payload.get("errors")
        if not isinstance(errors, list):
            return payload
        correlation_id = str(getattr(request.state, "correlation_id", ""))
        expected_codes = {"NOT_FOUND", "INVALID_INPUT", "INVALID_PAGINATION"}
        for raw_error in errors:
            if not isinstance(raw_error, dict):
                continue
            error = cast(dict[str, Any], raw_error)
            extensions = error.get("extensions")
            safe_extensions: dict[str, Any] = {}
            if isinstance(extensions, Mapping):
                typed_extensions = cast(Mapping[object, object], extensions)
                safe_extensions = {str(key): value for key, value in typed_extensions.items()}
            code = safe_extensions.get("code")
            if code not in expected_codes:
                safe_extensions["code"] = "GRAPHQL_REQUEST_REJECTED"
                error["message"] = "The GraphQL request could not be completed."
            if correlation_id:
                safe_extensions["correlation_id"] = correlation_id
            error["extensions"] = safe_extensions
        return payload


def forbidden() -> GraphQLError:
    return GraphQLError("The requested resource was not found.", extensions={"code": "NOT_FOUND"})


def page_limit(first: int) -> int:
    if first < 1 or first > 100:
        raise GraphQLError(
            "first must be between 1 and 100.", extensions={"code": "INVALID_PAGINATION"}
        )
    return first


@strawberry.type
class Query:
    @strawberry.field
    def current_user(self, info: strawberry.Info[GraphQLContext, None]) -> CurrentUserType:
        principal = info.context.principal
        return CurrentUserType(
            id=principal.user_id,
            email=principal.email,
            role=principal.role,
            preferred_language=principal.preferred_language,
        )

    @strawberry.field
    async def scans(
        self,
        info: strawberry.Info[GraphQLContext, None],
        first: int = 20,
        after: str | None = None,
    ) -> ScanConnection:
        limit = page_limit(first)
        cursor = None
        if after is not None:
            try:
                cursor = decode_scan_cursor(after)
            except (ValueError, TypeError) as error:
                raise GraphQLError(
                    "Invalid scan cursor.", extensions={"code": "INVALID_PAGINATION"}
                ) from error
        items, has_more = await info.context.queries.list_scans(
            info.context.principal, first=limit, after=cursor
        )
        return ScanConnection(
            items=[scan_type(item) for item in items],
            page_info=PageInfo(
                next_cursor=(
                    encode_scan_cursor(ScanCursor(items[-1].created_at, items[-1].id))
                    if has_more and items
                    else None
                )
            ),
        )

    @strawberry.field
    async def scan(self, info: strawberry.Info[GraphQLContext, None], id: UUID) -> ScanType | None:
        row = await info.context.loaders.scans.load(id)
        return scan_type(row) if row else None

    @strawberry.field
    async def garments(
        self,
        info: strawberry.Info[GraphQLContext, None],
        first: int = 20,
        after: str | None = None,
    ) -> GarmentConnection:
        limit = page_limit(first)
        cursor = None
        if after is not None:
            try:
                cursor = decode_garment_cursor(after)
            except (ValueError, TypeError) as error:
                raise GraphQLError(
                    "Invalid garment cursor.", extensions={"code": "INVALID_PAGINATION"}
                ) from error
        items, has_more = await info.context.queries.list_garments(
            info.context.principal, first=limit, after=cursor
        )
        return GarmentConnection(
            items=[garment_type(item) for item in items],
            page_info=PageInfo(
                next_cursor=(
                    encode_garment_cursor(GarmentCursor(items[-1].created_at, items[-1].id))
                    if has_more and items
                    else None
                )
            ),
        )

    @strawberry.field
    async def garment_history(
        self,
        info: strawberry.Info[GraphQLContext, None],
        first: int = 20,
        after: str | None = None,
    ) -> GarmentHistoryConnection:
        limit = page_limit(first)
        cursor = None
        if after is not None:
            try:
                cursor = decode_history_cursor(after)
            except ValueError as error:
                raise GraphQLError(
                    "Invalid garment history cursor.",
                    extensions={"code": "INVALID_PAGINATION"},
                ) from error
        items, has_more = await info.context.queries.list_garment_history(
            info.context.principal, first=limit, after=cursor
        )
        next_cursor = (
            encode_history_cursor(GarmentHistoryCursor(items[-1].last_analysis_at, items[-1].id))
            if has_more and items
            else None
        )
        return GarmentHistoryConnection(
            items=[garment_history_type(item) for item in items],
            page_info=PageInfo(next_cursor=next_cursor),
        )

    @strawberry.field
    async def garment(
        self, info: strawberry.Info[GraphQLContext, None], id: UUID
    ) -> GarmentType | None:
        row = await info.context.loaders.garments.load(id)
        return garment_type(row) if row else None

    @strawberry.field
    async def garment_detail(
        self,
        info: strawberry.Info[GraphQLContext, None],
        id: UUID,
        first: int = 20,
        after: str | None = None,
        language: str | None = None,
    ) -> GarmentDetailType | None:
        limit = page_limit(first)
        cursor = None
        if after is not None:
            try:
                cursor = decode_analysis_cursor(after)
            except ValueError as error:
                raise GraphQLError(
                    "Invalid garment analysis cursor.",
                    extensions={"code": "INVALID_PAGINATION"},
                ) from error
        requested_language = language or info.context.principal.preferred_language
        if requested_language not in {"en", "es"}:
            raise GraphQLError("language must be en or es.", extensions={"code": "INVALID_INPUT"})
        row = await info.context.queries.get_garment_detail(
            info.context.principal,
            id,
            first=limit,
            after=cursor,
            language=requested_language,
        )
        return garment_detail_type(row) if row else None

    @strawberry.field
    async def messages(
        self,
        info: strawberry.Info[GraphQLContext, None],
        scan_id: UUID,
        first: int = 30,
        after: str | None = None,
    ) -> ConversationMessageConnection:
        limit = page_limit(first)
        cursor = None
        if after is not None:
            try:
                cursor = decode_message_cursor(after)
            except (ValueError, TypeError) as error:
                raise GraphQLError(
                    "Invalid message cursor.", extensions={"code": "INVALID_PAGINATION"}
                ) from error
        items, has_more = await info.context.queries.list_messages(
            info.context.principal, scan_id=scan_id, first=limit, after=cursor
        )
        return ConversationMessageConnection(
            items=[message_type(item) for item in items],
            page_info=PageInfo(
                next_cursor=(
                    encode_message_cursor(MessageCursor(items[-1].created_at, items[-1].id))
                    if has_more and items
                    else None
                )
            ),
        )

    @strawberry.field
    async def analysis_revision(
        self, info: strawberry.Info[GraphQLContext, None], id: UUID
    ) -> AnalysisRevisionType | None:
        row = await info.context.loaders.revisions.load(id)
        return revision_type(row) if row else None

    @strawberry.field
    async def analysis(
        self, info: strawberry.Info[GraphQLContext, None], id: UUID
    ) -> AnalysisRevisionType | None:
        row = await info.context.loaders.revisions.load(id)
        return revision_type(row) if row else None

    @strawberry.field
    async def image_metadata(
        self, info: strawberry.Info[GraphQLContext, None], scan_id: UUID
    ) -> list[ScanImageMetadataType]:
        rows = await info.context.loaders.images.load(scan_id)
        if rows is None:
            raise forbidden()
        return [image_metadata_type(row) for row in rows]

    @strawberry.field
    async def run(self, info: strawberry.Info[GraphQLContext, None], id: UUID) -> AiRunType | None:
        row = await info.context.loaders.runs.load(id)
        return ai_run_type(row) if row else None

    @strawberry.field
    async def usage(self, info: strawberry.Info[GraphQLContext, None]) -> UsageSummary:
        usage = await info.context.queries.get_usage(info.context.principal)
        if usage is None:
            raise forbidden()
        return UsageSummary(
            model_run_count=usage.model_run_count,
            estimated_cost_usd=str(usage.estimated_cost_usd),
        )

    @strawberry.field
    async def scan_result(
        self,
        info: strawberry.Info[GraphQLContext, None],
        scan_id: UUID,
        language: str | None = None,
    ) -> ResultCompositeType | None:
        requested_language = language or info.context.principal.preferred_language
        if requested_language not in {"en", "es"}:
            raise GraphQLError("language must be en or es.", extensions={"code": "INVALID_INPUT"})
        row = await info.context.queries.get_result_composite(
            info.context.principal, scan_id, language=requested_language
        )
        return result_composite_type(row) if row else None


def scan_type(row: ScanView) -> ScanType:
    return ScanType(
        id=row.id,
        status=row.status,
        requested_language=row.requested_language,
        progress_percent=row.progress_percent,
        analysis_stage=row.analysis_stage,
        error_code=row.error_code,
        garment_id=row.garment_id,
        created_at=row.created_at,
    )


def garment_type(row: GarmentView) -> GarmentType:
    return GarmentType(
        id=row.id,
        display_name=row.display_name,
        archived_at=row.archived_at,
        active_result_id=row.active_result_id,
        created_at=row.created_at,
    )


def garment_history_type(row: GarmentHistoryView) -> GarmentHistoryItemType:
    return GarmentHistoryItemType(
        id=row.id,
        identifiers=row.identifiers,
        # GraphQL returns safe image identifiers only. Preview/download remains REST.
        thumbnail_url=None,
        thumbnail_scan_id=row.thumbnail_scan_id,
        thumbnail_image_id=row.thumbnail_image_id,
        last_analysis_at=row.last_analysis_at,
        analysed_before=row.analysed_before,
        cleaned_before=row.cleaned_before,
    )


def service_event_type(row: ServiceEventView) -> ServiceEventType:
    return ServiceEventType(
        id=row.id,
        kind=row.kind,
        note=row.note,
        created_at=row.created_at,
    )


def garment_analysis_history_type(row: GarmentAnalysisHistoryView) -> GarmentAnalysisHistoryType:
    return GarmentAnalysisHistoryType(
        scan_id=row.scan_id,
        status=row.status,
        created_at=row.created_at,
        result_available=row.result_available,
        thumbnail_scan_id=row.thumbnail_scan_id,
        thumbnail_image_id=row.thumbnail_image_id,
    )


def garment_detail_type(row: GarmentDetailView) -> GarmentDetailType:
    next_cursor = (
        encode_analysis_cursor(
            GarmentAnalysisCursor(row.analyses[-1].created_at, row.analyses[-1].scan_id)
        )
        if row.analyses_has_more and row.analyses
        else None
    )
    return GarmentDetailType(
        id=row.id,
        display_name=row.display_name,
        identifiers=row.identifiers,
        thumbnail_scan_id=row.thumbnail_scan_id,
        thumbnail_image_id=row.thumbnail_image_id,
        last_analysis_at=row.last_analysis_at,
        analysed_before=row.analysed_before,
        cleaned_before=row.cleaned_before,
        active_analysis=(
            revision_type(row.active_analysis) if row.active_analysis is not None else None
        ),
        active_result=care_result_type(row.active_result)
        if row.active_result is not None
        else None,
        analyses=GarmentAnalysisHistoryConnection(
            items=[garment_analysis_history_type(item) for item in row.analyses],
            page_info=PageInfo(next_cursor=next_cursor),
        ),
        service_events=[service_event_type(event) for event in row.service_events],
    )


def message_type(row: ConversationMessageView) -> ConversationMessageType:
    return ConversationMessageType(
        id=row.id, role=row.role, status=row.status, text=row.text, created_at=row.created_at
    )


def revision_type(row: AnalysisRevisionView) -> AnalysisRevisionType:
    return AnalysisRevisionType(
        id=row.id,
        scan_id=row.scan_id,
        status=row.status,
        revision_number=row.revision_number,
        created_at=row.created_at,
    )


def image_metadata_type(row: ImageMetadataView) -> ScanImageMetadataType:
    return ScanImageMetadataType(
        id=row.id,
        role=row.role,
        display_order=row.display_order,
        width=row.width,
        height=row.height,
    )


def ai_run_type(row: RunView) -> AiRunType:
    return AiRunType(
        id=row.id,
        scan_id=row.scan_id,
        operation=row.operation,
        status=row.status,
        error_code=row.error_code,
        created_at=row.created_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def care_result_type(row: CareResultView) -> CareResultType:
    return CareResultType(
        id=row.id, status=row.status, language=row.language, data=cast(JSON, row.data)
    )


def identity_candidate_type(row: IdentityCandidateView) -> IdentityCandidateType:
    return IdentityCandidateType(
        id=row.id,
        garment_id=row.garment_id,
        thumbnail_scan_id=row.thumbnail_scan_id,
        thumbnail_image_id=row.thumbnail_image_id,
        classification=row.classification,
        reasons=cast(JSON, row.reasons),
        status=row.status,
    )


def result_composite_type(row: ResultCompositeView) -> ResultCompositeType:
    return ResultCompositeType(
        scan=scan_type(row.scan),
        active_analysis=(
            revision_type(row.active_analysis) if row.active_analysis is not None else None
        ),
        result=care_result_type(row.result) if row.result is not None else None,
        garment=garment_type(row.garment) if row.garment is not None else None,
        identity_candidates=[identity_candidate_type(item) for item in row.identity_candidates],
    )


def create_schema(settings: Settings) -> strawberry.Schema:
    """Build the query-only schema used both by FastAPI and code generation."""
    extensions: list[type[SchemaExtension] | SchemaExtension] = [
        QueryDepthLimiter(max_depth=settings.graphql_max_depth),
        MaxTokensLimiter(max_token_count=settings.graphql_max_tokens),
        MaxAliasesLimiter(max_alias_count=settings.graphql_max_aliases),
    ]
    if settings.environment == "production":
        extensions.append(DisableIntrospection)
    return strawberry.Schema(query=Query, extensions=extensions)


def create_graphql_router(*, context_getter: object, settings: Settings) -> GraphQLRouter:
    """Mount GraphQL with production-safe IDE/introspection/depth policy."""
    return FabricAssistGraphQLRouter(
        create_schema(settings),
        context_getter=context_getter,  # type: ignore[arg-type]
        graphql_ide=None if settings.environment == "production" else "graphiql",
    )
