"""FastAPI application factory for the Phase 2 backend foundation."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.metadata import version
from secrets import compare_digest
from typing import cast

import jwt
from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import ExceptionHandler

from fabricassist.api.errors import (
    ApiError,
    api_error_handler,
    http_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from fabricassist.api.graphql_loaders import GraphQLLoaders
from fabricassist.api.graphql_schema import GraphQLContext, create_graphql_router
from fabricassist.api.logging import configure_logging
from fabricassist.api.middleware import (
    CorrelationIdMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from fabricassist.api.routes import (
    auth,
    conversations,
    garments,
    internal_jobs,
    products,
    reviews,
    runs,
    scans,
)
from fabricassist.application.auth import decode_access_token
from fabricassist.application.object_storage import ObjectStorage
from fabricassist.application.policies import (
    AnalysisExecutionPolicy,
    ConversationPolicy,
    JobExecutionPolicy,
    ProductLookupPolicy,
    UploadPolicy,
)
from fabricassist.application.publication_recovery import (
    publication_recovery_loop,
    stop_recovery_task,
)
from fabricassist.application.storefront_queries import StorefrontPrincipal, StorefrontQueryPort
from fabricassist.infrastructure.cache.factory import create_hot_cache
from fabricassist.infrastructure.concurrency.factory import create_concurrency_gate
from fabricassist.infrastructure.database import Database, DatabasePort
from fabricassist.infrastructure.garment_analysis import create_garment_analysis_workflow
from fabricassist.infrastructure.jobs.factory import create_job_dispatcher
from fabricassist.infrastructure.jobs.qstash_inbound import (
    create_qstash_delivery_verifier,
)
from fabricassist.infrastructure.operational_metrics import durable_metrics
from fabricassist.infrastructure.persistence.models import User
from fabricassist.infrastructure.persistence.storefront_queries import (
    SqlAlchemyStorefrontQueries,
)
from fabricassist.infrastructure.product_information.factory import (
    create_product_information_provider,
)
from fabricassist.infrastructure.rate_limits.factory import create_rate_limiter
from fabricassist.infrastructure.storage.factory import create_object_storage
from fabricassist.infrastructure.telemetry import configure_telemetry, metrics_payload
from fabricassist.infrastructure.vision.providers import (
    create_conversation_provider,
    create_evidence_provider,
)
from fabricassist.settings import Settings


def create_app(
    settings: Settings | None = None,
    database: DatabasePort | None = None,
) -> FastAPI:
    """Compose the API foundation without any business feature routes."""
    resolved_settings = settings or Settings()
    resolved_database = database or Database.from_settings(resolved_settings)
    rate_limiter = create_rate_limiter(resolved_settings)
    job_dispatcher = create_job_dispatcher(resolved_settings)
    qstash_verifier = create_qstash_delivery_verifier(
        resolved_settings.qstash_current_signing_key,
        resolved_settings.qstash_next_signing_key,
        resolved_settings.qstash_destination_url,
    )
    hot_cache = create_hot_cache(resolved_settings)
    concurrency_gate = create_concurrency_gate(resolved_settings)
    evidence_provider = create_evidence_provider(resolved_settings)
    conversation_provider = create_conversation_provider(resolved_settings)
    product_information_provider = create_product_information_provider(resolved_settings)
    storage = create_object_storage(resolved_settings)
    garment_analysis_workflow = (
        create_garment_analysis_workflow(
            database=resolved_database, storage=storage, settings=resolved_settings
        )
        if isinstance(resolved_database, Database)
        else None
    )
    analysis_policy = AnalysisExecutionPolicy(
        hot_cache_ttl_seconds=resolved_settings.cache_hot_ttl_seconds,
        product_cache_minutes=resolved_settings.product_cache_minutes,
    )
    job_execution_policy = JobExecutionPolicy(
        stage_budget_seconds=resolved_settings.job_stage_budget_seconds
    )
    conversation_policy = ConversationPolicy(
        recent_message_limit=resolved_settings.conversation_recent_message_limit,
        relevant_image_limit=resolved_settings.conversation_relevant_image_limit,
    )
    product_lookup_policy = ProductLookupPolicy(
        cache_minutes=resolved_settings.product_cache_minutes
    )
    upload_policy = UploadPolicy(max_images_per_scan=resolved_settings.max_images_per_scan)
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        recovery_task: asyncio.Task[None] | None = None
        if isinstance(resolved_database, Database):
            recovery_task = asyncio.create_task(
                publication_recovery_loop(
                    database=resolved_database,
                    dispatcher=job_dispatcher,
                    storage=storage,
                    interval_seconds=resolved_settings.publication_recovery_interval_seconds,
                    batch_size=resolved_settings.publication_recovery_batch_size,
                    deletion_max_attempts=resolved_settings.deletion_max_attempts,
                ),
                name="fabricassist-durable-recovery",
            )
        try:
            yield
        finally:
            try:
                await stop_recovery_task(recovery_task)
            finally:
                try:
                    await rate_limiter.close()
                finally:
                    await resolved_database.close()

    app = FastAPI(
        title="FabricAssist API",
        version=version("fabricassist"),
        description="Validated garment intelligence, review, and lifecycle API.",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.database = resolved_database
    app.state.storage = storage
    app.state.garment_analysis_workflow = garment_analysis_workflow
    app.state.job_dispatcher = job_dispatcher
    app.state.qstash_verifier = qstash_verifier
    app.state.hot_cache = hot_cache
    app.state.concurrency_gate = concurrency_gate
    app.state.evidence_provider = evidence_provider
    app.state.conversation_provider = conversation_provider
    app.state.product_information_provider = product_information_provider
    app.state.analysis_policy = analysis_policy
    app.state.job_execution_policy = job_execution_policy
    app.state.conversation_policy = conversation_policy
    app.state.product_lookup_policy = product_lookup_policy
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin for origin in resolved_settings.cors_allowed_origins.split(",") if origin
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-CSRF-Token",
            "X-Correlation-ID",
            "Last-Event-ID",
        ],
    )
    app.add_middleware(
        RateLimitMiddleware,
        settings=resolved_settings,
        limiter=rate_limiter,
    )
    app.add_middleware(SecurityHeadersMiddleware, settings=resolved_settings)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_exception_handler(ApiError, cast(ExceptionHandler, api_error_handler))
    app.add_exception_handler(Exception, cast(ExceptionHandler, unexpected_error_handler))
    app.add_exception_handler(StarletteHTTPException, cast(ExceptionHandler, http_error_handler))
    app.add_exception_handler(
        RequestValidationError, cast(ExceptionHandler, validation_error_handler)
    )

    def get_database(request: Request) -> DatabasePort:
        return request.app.state.database  # type: ignore[no-any-return]

    def get_runtime_database(request: Request) -> Database:
        database_instance = request.app.state.database
        if not isinstance(database_instance, Database):
            raise ApiError(503, "DEPENDENCY_UNAVAILABLE", "Database runtime is unavailable.")
        return database_instance

    async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
        database_instance = request.app.state.database
        if not isinstance(database_instance, Database):
            raise ApiError(503, "DEPENDENCY_UNAVAILABLE", "Database sessions are unavailable.")
        async with database_instance.session_factory() as session:
            yield session

    def get_settings(request: Request) -> Settings:
        return request.app.state.settings  # type: ignore[no-any-return]

    def get_storage(request: Request) -> ObjectStorage:
        return request.app.state.storage  # type: ignore[no-any-return]

    def get_garment_analysis_workflow(request: Request) -> object:
        workflow = request.app.state.garment_analysis_workflow
        if workflow is None:
            raise ApiError(503, "DEPENDENCY_UNAVAILABLE", "Analysis workflow is unavailable.")
        return workflow

    async def get_storefront_queries(
        session: AsyncSession = Depends(get_session),  # noqa: B008
        storage: ObjectStorage = Depends(get_storage),  # noqa: B008
    ) -> StorefrontQueryPort:
        return SqlAlchemyStorefrontQueries(session, storage=storage)

    def get_job_dispatcher(request: Request) -> object:
        return request.app.state.job_dispatcher

    def get_qstash_verifier(request: Request) -> object:
        return request.app.state.qstash_verifier

    def get_hot_cache(request: Request) -> object:
        return request.app.state.hot_cache

    def get_concurrency_gate(request: Request) -> object:
        return request.app.state.concurrency_gate

    def get_evidence_provider(request: Request) -> object:
        return request.app.state.evidence_provider

    def get_conversation_provider(request: Request) -> object:
        return request.app.state.conversation_provider

    def get_product_information_provider(request: Request) -> object:
        return request.app.state.product_information_provider

    def get_analysis_policy(request: Request) -> object:
        return request.app.state.analysis_policy

    def get_job_execution_policy(request: Request) -> object:
        return request.app.state.job_execution_policy

    def get_conversation_policy(request: Request) -> object:
        return request.app.state.conversation_policy

    def get_product_lookup_policy(request: Request) -> object:
        return request.app.state.product_lookup_policy

    bearer = HTTPBearer(auto_error=False)

    async def get_current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),  # noqa: B008
        session: AsyncSession = Depends(get_session),  # noqa: B008
    ) -> User:
        if credentials is None:
            raise ApiError(401, "UNAUTHENTICATED", "Authentication is required.")
        try:
            claims = decode_access_token(credentials.credentials, resolved_settings)
            user = await session.get(User, claims["sub"])
        except jwt.InvalidTokenError as error:
            raise ApiError(401, "UNAUTHENTICATED", "Authentication is required.") from error
        if (
            user is None
            or not user.is_active
            or str(user.tenant_id) != claims["tenant_id"]
            or user.role != claims["role"]
        ):
            raise ApiError(401, "UNAUTHENTICATED", "Authentication is required.")
        return user

    app.dependency_overrides[auth.get_session] = get_session
    app.dependency_overrides[auth.get_settings] = get_settings
    app.dependency_overrides[garments.get_session] = get_session
    app.dependency_overrides[garments.get_current_user] = get_current_user
    app.dependency_overrides[garments.get_storage] = get_storage
    app.dependency_overrides[garments.get_storefront_queries] = get_storefront_queries
    app.dependency_overrides[scans.get_session] = get_session
    app.dependency_overrides[scans.get_current_user] = get_current_user
    app.dependency_overrides[scans.get_storage] = get_storage
    app.dependency_overrides[scans.get_upload_policy] = lambda: upload_policy
    app.dependency_overrides[scans.get_job_dispatcher] = get_job_dispatcher
    app.dependency_overrides[scans.get_settings] = get_settings
    app.dependency_overrides[runs.get_session] = get_session
    app.dependency_overrides[runs.get_current_user] = get_current_user
    app.dependency_overrides[runs.get_job_dispatcher] = get_job_dispatcher
    app.dependency_overrides[runs.get_database] = get_runtime_database
    app.dependency_overrides[products.get_session] = get_session
    app.dependency_overrides[products.get_current_user] = get_current_user
    app.dependency_overrides[products.get_product_information_provider] = (
        get_product_information_provider
    )
    app.dependency_overrides[products.get_product_lookup_policy] = get_product_lookup_policy
    app.dependency_overrides[conversations.get_session] = get_session
    app.dependency_overrides[conversations.get_current_user] = get_current_user
    app.dependency_overrides[conversations.get_job_dispatcher] = get_job_dispatcher
    app.dependency_overrides[reviews.get_session] = get_session
    app.dependency_overrides[reviews.get_current_user] = get_current_user
    app.dependency_overrides[internal_jobs.get_session] = get_session
    app.dependency_overrides[internal_jobs.get_database] = get_runtime_database
    app.dependency_overrides[internal_jobs.get_job_dispatcher] = get_job_dispatcher
    app.dependency_overrides[internal_jobs.get_qstash_verifier] = get_qstash_verifier
    app.dependency_overrides[internal_jobs.get_concurrency_gate] = get_concurrency_gate
    app.dependency_overrides[internal_jobs.get_garment_analysis_workflow] = (
        get_garment_analysis_workflow
    )
    app.dependency_overrides[internal_jobs.get_conversation_provider] = get_conversation_provider
    app.dependency_overrides[internal_jobs.get_job_execution_policy] = get_job_execution_policy
    app.dependency_overrides[internal_jobs.get_conversation_policy] = get_conversation_policy
    app.include_router(auth.router)
    app.include_router(scans.router)
    app.include_router(runs.router)
    app.include_router(garments.router)
    app.include_router(products.router)
    app.include_router(conversations.router)
    app.include_router(reviews.router)
    app.include_router(internal_jobs.router)

    async def graphql_context(
        request: Request,
        user: User = Depends(get_current_user),  # noqa: B008
        session: AsyncSession = Depends(get_session),  # noqa: B008
    ) -> GraphQLContext:
        principal = StorefrontPrincipal(
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            role=user.role,
            preferred_language=user.preferred_language,
        )
        queries = SqlAlchemyStorefrontQueries(session)
        return GraphQLContext(
            principal=principal,
            correlation_id=str(getattr(request.state, "correlation_id", "")),
            queries=queries,
            loaders=GraphQLLoaders(queries, principal),
        )

    app.include_router(
        create_graphql_router(context_getter=graphql_context, settings=resolved_settings),
        prefix="/api/v1/graphql",
        tags=["graphql"],
    )

    @app.get("/api/v1/health/live", tags=["health"])
    async def live(response: Response) -> dict[str, str]:
        """Report process liveness without checking dependencies."""
        response.headers["X-FabricAssist-Revision"] = os.environ.get("RENDER_GIT_COMMIT", "local")
        return {"status": "ok"}

    @app.get("/api/v1/health/ready", tags=["health"])
    async def ready(
        database_dependency: DatabasePort = Depends(get_database),  # noqa: B008
    ) -> dict[str, str]:
        """Report readiness only when PostgreSQL accepts a safe probe."""
        if not await database_dependency.is_available():
            raise ApiError(503, "DEPENDENCY_UNAVAILABLE", "Service dependencies are unavailable.")
        if resolved_settings.environment == "production" and (
            not resolved_settings.garment_analysis_enabled
            or not resolved_settings.garment_analysis_privacy_approved
            or app.state.garment_analysis_workflow is None
        ):
            raise ApiError(
                503,
                "ANALYSIS_GATE_NOT_READY",
                "The current garment-analysis workflow is not approved and ready.",
            )
        return {"status": "ok"}

    @app.get("/api/v1/bootstrap", tags=["health"])
    async def bootstrap(
        database_dependency: DatabasePort = Depends(get_database),  # noqa: B008
    ) -> dict[str, str]:
        """Warm only the API and database dependencies needed for sign-in.

        It has no request body, authentication state, or user-specific response.
        In particular, it does not contact the job dispatcher, object storage,
        vision, or product-information providers.
        """
        if not await database_dependency.is_available():
            raise ApiError(503, "DEPENDENCY_UNAVAILABLE", "Service dependencies are unavailable.")
        return {"status": "ok"}

    @app.get(
        "/api/v1/metrics",
        tags=["operations"],
        include_in_schema=False,
        response_class=Response,
    )
    async def metrics(
        authorization: str | None = Header(default=None),
    ) -> Response:
        """Expose internal metrics only when enabled and authorized."""
        if not resolved_settings.metrics_enabled:
            raise ApiError(404, "NOT_FOUND", "The requested resource was not found.")
        if resolved_settings.metrics_access_token:
            supplied = (
                authorization.removeprefix("Bearer ")
                if authorization and authorization.startswith("Bearer ")
                else ""
            )
            if not compare_digest(supplied, resolved_settings.metrics_access_token):
                raise ApiError(401, "UNAUTHENTICATED", "Authentication is required.")
        payload, content_type = metrics_payload()
        if isinstance(resolved_database, Database):
            async with resolved_database.session_factory() as session:
                payload += await durable_metrics(session)
        return Response(content=payload, media_type=content_type)

    configure_telemetry(app, resolved_settings)
    return app


app = create_app()
