"""Strawberry schema for canonical authenticated FabricAssist reads."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import strawberry
from graphql import GraphQLError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from strawberry.extensions import (
    DisableIntrospection,
    MaxAliasesLimiter,
    MaxTokensLimiter,
    QueryDepthLimiter,
)
from strawberry.extensions.base_extension import SchemaExtension
from strawberry.fastapi import GraphQLRouter
from strawberry.http import GraphQLHTTPResponse
from strawberry.types.execution import ExecutionResult

from fabricassist.infrastructure.persistence.models import (
    AiRun,
    AnalysisRevision,
    ConversationMessage,
    ConversationThread,
    CustomerFeedback,
    Garment,
    ModelRun,
    Scan,
    ScanImage,
    User,
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
class FeedbackType:
    id: UUID
    request_review: bool


@strawberry.input
class CreateScanInput:
    requested_language: str = "en"


@strawberry.input
class RenameGarmentInput:
    garment_id: UUID
    display_name: str


@strawberry.input
class GarmentIdInput:
    garment_id: UUID


@strawberry.input
class ScanIdInput:
    scan_id: UUID


@strawberry.input
class SubmitFeedbackInput:
    scan_id: UUID
    rating: int | None = None
    comment: str | None = None
    request_review: bool = False


class GraphQLContext:
    def __init__(self, *, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user


class FabricAssistGraphQLRouter(GraphQLRouter):
    """Keep GraphQL error details as deliberately small as the REST envelope."""

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
        user = info.context.user
        return CurrentUserType(
            id=user.id,
            email=user.email,
            role=user.role,
            preferred_language=user.preferred_language,
        )

    @strawberry.field
    async def scans(
        self,
        info: strawberry.Info[GraphQLContext, None],
        first: int = 20,
        after: UUID | None = None,
    ) -> ScanConnection:
        limit = page_limit(first)
        statement = select(Scan).where(
            Scan.tenant_id == info.context.user.tenant_id,
            Scan.user_id == info.context.user.id,
            Scan.status != "deleted",
        )
        if after is not None:
            previous = await info.context.session.scalar(
                select(Scan).where(Scan.id == after, Scan.user_id == info.context.user.id)
            )
            if previous is None:
                raise forbidden()
            statement = statement.where(
                (Scan.created_at < previous.created_at)
                | ((Scan.created_at == previous.created_at) & (Scan.id < previous.id))
            )
        rows = list(
            (
                await info.context.session.scalars(
                    statement.order_by(Scan.created_at.desc(), Scan.id.desc()).limit(limit + 1)
                )
            ).all()
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        return ScanConnection(
            items=[scan_type(row) for row in rows],
            page_info=PageInfo(next_cursor=str(rows[-1].id) if has_more and rows else None),
        )

    @strawberry.field
    async def scan(self, info: strawberry.Info[GraphQLContext, None], id: UUID) -> ScanType | None:
        row = await owned_scan(info.context, id)
        return scan_type(row) if row else None

    @strawberry.field
    async def garments(
        self,
        info: strawberry.Info[GraphQLContext, None],
        first: int = 20,
        after: UUID | None = None,
    ) -> GarmentConnection:
        limit = page_limit(first)
        statement = select(Garment).where(
            Garment.tenant_id == info.context.user.tenant_id,
            Garment.user_id == info.context.user.id,
            Garment.archived_at.is_(None),
        )
        if after is not None:
            statement = statement.where(Garment.id < after)
        rows = list(
            (
                await info.context.session.scalars(
                    statement.order_by(Garment.id.desc()).limit(limit + 1)
                )
            ).all()
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        return GarmentConnection(
            items=[garment_type(row) for row in rows],
            page_info=PageInfo(next_cursor=str(rows[-1].id) if has_more and rows else None),
        )

    @strawberry.field
    async def garment(
        self, info: strawberry.Info[GraphQLContext, None], id: UUID
    ) -> GarmentType | None:
        row = await owned_garment(info.context, id)
        return garment_type(row) if row else None

    @strawberry.field
    async def messages(
        self,
        info: strawberry.Info[GraphQLContext, None],
        scan_id: UUID,
        first: int = 30,
        after: UUID | None = None,
    ) -> ConversationMessageConnection:
        limit = page_limit(first)
        scan = await owned_scan(info.context, scan_id)
        if scan is None or scan.garment_id is None:
            return ConversationMessageConnection(items=[], page_info=PageInfo(next_cursor=None))
        thread = await info.context.session.scalar(
            select(ConversationThread).where(
                ConversationThread.tenant_id == info.context.user.tenant_id,
                ConversationThread.garment_id == scan.garment_id,
                ConversationThread.user_id == info.context.user.id,
            )
        )
        if thread is None:
            return ConversationMessageConnection(items=[], page_info=PageInfo(next_cursor=None))
        statement = select(ConversationMessage).where(ConversationMessage.thread_id == thread.id)
        if after is not None:
            previous = await info.context.session.scalar(
                select(ConversationMessage).where(
                    ConversationMessage.id == after, ConversationMessage.thread_id == thread.id
                )
            )
            if previous is None:
                raise forbidden()
            statement = statement.where(
                (ConversationMessage.created_at > previous.created_at)
                | (
                    (ConversationMessage.created_at == previous.created_at)
                    & (ConversationMessage.id > previous.id)
                )
            )
        rows = list(
            (
                await info.context.session.scalars(
                    statement.order_by(
                        ConversationMessage.created_at, ConversationMessage.id
                    ).limit(limit + 1)
                )
            ).all()
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        return ConversationMessageConnection(
            items=[message_type(row) for row in rows],
            page_info=PageInfo(next_cursor=str(rows[-1].id) if has_more and rows else None),
        )

    @strawberry.field
    async def analysis_revision(
        self, info: strawberry.Info[GraphQLContext, None], id: UUID
    ) -> AnalysisRevisionType | None:
        row = await info.context.session.scalar(
            select(AnalysisRevision)
            .join(Scan, Scan.id == AnalysisRevision.scan_id)
            .where(
                AnalysisRevision.id == id,
                AnalysisRevision.tenant_id == info.context.user.tenant_id,
                Scan.user_id == info.context.user.id,
            )
        )
        return revision_type(row) if row else None

    @strawberry.field
    async def analysis(
        self, info: strawberry.Info[GraphQLContext, None], id: UUID
    ) -> AnalysisRevisionType | None:
        """Compatibility-friendly conceptual analysis lookup for typed clients."""
        row = await info.context.session.scalar(
            select(AnalysisRevision)
            .join(Scan, Scan.id == AnalysisRevision.scan_id)
            .where(
                AnalysisRevision.id == id,
                AnalysisRevision.tenant_id == info.context.user.tenant_id,
                Scan.user_id == info.context.user.id,
            )
        )
        return revision_type(row) if row else None

    @strawberry.field
    async def image_metadata(
        self, info: strawberry.Info[GraphQLContext, None], scan_id: UUID
    ) -> list[ScanImageMetadataType]:
        scan = await owned_scan(info.context, scan_id)
        if scan is None:
            raise forbidden()
        rows = list(
            (
                await info.context.session.scalars(
                    select(ScanImage)
                    .where(
                        ScanImage.scan_id == scan.id,
                        ScanImage.tenant_id == info.context.user.tenant_id,
                        ScanImage.completed_at.is_not(None),
                        ScanImage.deleted_at.is_(None),
                    )
                    .order_by(ScanImage.display_order, ScanImage.created_at)
                )
            ).all()
        )
        return [
            ScanImageMetadataType(
                id=row.id,
                role=row.role,
                display_order=row.display_order,
                width=row.width,
                height=row.height,
            )
            for row in rows
        ]

    @strawberry.field
    async def run(self, info: strawberry.Info[GraphQLContext, None], id: UUID) -> AiRunType | None:
        row = await info.context.session.scalar(
            select(AiRun).where(
                AiRun.id == id,
                AiRun.tenant_id == info.context.user.tenant_id,
                AiRun.user_id == info.context.user.id,
            )
        )
        return ai_run_type(row) if row else None

    @strawberry.field
    async def usage(self, info: strawberry.Info[GraphQLContext, None]) -> UsageSummary:
        if info.context.user.role != "admin":
            raise forbidden()
        result = await info.context.session.execute(
            select(
                func.count(ModelRun.id), func.coalesce(func.sum(ModelRun.estimated_cost_usd), 0)
            ).where(ModelRun.tenant_id == info.context.user.tenant_id)
        )
        count, cost = cast(tuple[int, Decimal | None], result.one())
        return UsageSummary(model_run_count=count, estimated_cost_usd=str(cost or Decimal(0)))


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_scan(
        self, info: strawberry.Info[GraphQLContext, None], input: CreateScanInput
    ) -> ScanType:
        if input.requested_language not in {"en", "es"}:
            raise GraphQLError("Unsupported language.", extensions={"code": "INVALID_INPUT"})
        scan = Scan(
            id=uuid4(),
            tenant_id=info.context.user.tenant_id,
            user_id=info.context.user.id,
            requested_language=input.requested_language,
            status="draft",
        )
        info.context.session.add(scan)
        await info.context.session.commit()
        return scan_type(scan)

    @strawberry.mutation
    async def rename_garment(
        self, info: strawberry.Info[GraphQLContext, None], input: RenameGarmentInput
    ) -> GarmentType:
        garment = await owned_garment(info.context, input.garment_id)
        if garment is None:
            raise forbidden()
        display_name = input.display_name.strip()
        if len(display_name) > 200:
            raise GraphQLError("Display name is too long.", extensions={"code": "INVALID_INPUT"})
        garment.display_name = display_name or None
        await info.context.session.commit()
        return garment_type(garment)

    @strawberry.mutation
    async def archive_garment(
        self, info: strawberry.Info[GraphQLContext, None], input: GarmentIdInput
    ) -> GarmentType:
        garment = await owned_garment(info.context, input.garment_id)
        if garment is None:
            raise forbidden()
        garment.archived_at = datetime.now(UTC)
        await info.context.session.commit()
        return garment_type(garment)

    @strawberry.mutation
    async def unarchive_garment(
        self, info: strawberry.Info[GraphQLContext, None], input: GarmentIdInput
    ) -> GarmentType:
        garment = await owned_garment(info.context, input.garment_id)
        if garment is None:
            raise forbidden()
        garment.archived_at = None
        await info.context.session.commit()
        return garment_type(garment)

    @strawberry.mutation
    async def delete_scan(
        self, info: strawberry.Info[GraphQLContext, None], input: ScanIdInput
    ) -> bool:
        scan = await owned_scan(info.context, input.scan_id)
        if scan is None:
            raise forbidden()
        scan.status = "deleted"
        await info.context.session.commit()
        return True

    @strawberry.mutation
    async def delete_garment(
        self, info: strawberry.Info[GraphQLContext, None], input: GarmentIdInput
    ) -> bool:
        garment = await owned_garment(info.context, input.garment_id)
        if garment is None:
            raise forbidden()
        garment.archived_at = datetime.now(UTC)
        await info.context.session.commit()
        return True

    @strawberry.mutation
    async def submit_feedback(
        self, info: strawberry.Info[GraphQLContext, None], input: SubmitFeedbackInput
    ) -> FeedbackType:
        scan = await owned_scan(info.context, input.scan_id)
        if scan is None:
            raise forbidden()
        if input.rating is not None and not 1 <= input.rating <= 5:
            raise GraphQLError(
                "Rating must be between 1 and 5.", extensions={"code": "INVALID_INPUT"}
            )
        if input.comment is not None and len(input.comment) > 2_000:
            raise GraphQLError("Comment is too long.", extensions={"code": "INVALID_INPUT"})
        feedback = CustomerFeedback(
            id=uuid4(),
            tenant_id=info.context.user.tenant_id,
            scan_id=scan.id,
            user_id=info.context.user.id,
            rating=input.rating,
            comment=input.comment,
            request_review=input.request_review,
        )
        info.context.session.add(feedback)
        await info.context.session.commit()
        return FeedbackType(id=feedback.id, request_review=feedback.request_review)


async def owned_scan(context: GraphQLContext, scan_id: UUID) -> Scan | None:
    return await context.session.scalar(
        select(Scan).where(
            Scan.id == scan_id,
            Scan.tenant_id == context.user.tenant_id,
            Scan.user_id == context.user.id,
        )
    )


async def owned_garment(context: GraphQLContext, garment_id: UUID) -> Garment | None:
    return await context.session.scalar(
        select(Garment).where(
            Garment.id == garment_id,
            Garment.tenant_id == context.user.tenant_id,
            Garment.user_id == context.user.id,
            Garment.archived_at.is_(None),
        )
    )


def scan_type(row: Scan) -> ScanType:
    return ScanType(
        id=row.id,
        status=row.status,
        requested_language=row.requested_language,
        progress_percent=row.progress_percent,
        analysis_stage=row.analysis_stage,
        error_code=row.analysis_error_code,
        garment_id=row.garment_id,
        created_at=row.created_at,
    )


def garment_type(row: Garment) -> GarmentType:
    return GarmentType(
        id=row.id,
        display_name=row.display_name,
        archived_at=row.archived_at,
        active_result_id=row.active_result_id,
        created_at=row.created_at,
    )


def message_type(row: ConversationMessage) -> ConversationMessageType:
    return ConversationMessageType(
        id=row.id, role=row.role, status=row.status, text=row.text, created_at=row.created_at
    )


def revision_type(row: AnalysisRevision) -> AnalysisRevisionType:
    return AnalysisRevisionType(
        id=row.id,
        scan_id=row.scan_id,
        status=row.status,
        revision_number=row.revision_number,
        created_at=row.created_at,
    )


def ai_run_type(row: AiRun) -> AiRunType:
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


def create_schema(settings: Settings) -> strawberry.Schema:
    """Build the deterministic schema used both by FastAPI and code generation."""
    extensions: list[type[SchemaExtension] | SchemaExtension] = [
        QueryDepthLimiter(max_depth=settings.graphql_max_depth),
        # Token and alias ceilings make query cost bounded even while the
        # schema remains deliberately shallow and cursor-paginated.
        MaxTokensLimiter(max_token_count=settings.graphql_max_tokens),
        MaxAliasesLimiter(max_alias_count=settings.graphql_max_aliases),
    ]
    if settings.environment == "production":
        extensions.append(DisableIntrospection)
    return strawberry.Schema(query=Query, mutation=Mutation, extensions=extensions)


def create_graphql_router(*, context_getter: object, settings: Settings) -> GraphQLRouter:
    """Mount GraphQL with production-safe IDE/introspection/depth policy."""
    return FabricAssistGraphQLRouter(
        create_schema(settings),
        context_getter=context_getter,  # type: ignore[arg-type]
        graphql_ide=None if settings.environment == "production" else "graphiql",
    )
