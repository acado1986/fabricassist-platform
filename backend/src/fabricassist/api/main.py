"""FastAPI application factory for the Phase 2 backend foundation."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast

import jwt
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ExceptionHandler

from fabricassist.api.errors import (
    ApiError,
    api_error_handler,
    http_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from fabricassist.api.logging import configure_logging
from fabricassist.api.middleware import CorrelationIdMiddleware
from fabricassist.api.routes import auth, scans
from fabricassist.application.auth import decode_access_token
from fabricassist.infrastructure.database import Database, DatabasePort
from fabricassist.infrastructure.persistence.models import User
from fabricassist.infrastructure.storage.s3 import S3Storage
from fabricassist.settings import Settings


def create_app(
    settings: Settings | None = None,
    database: DatabasePort | None = None,
) -> FastAPI:
    """Compose the API foundation without any business feature routes."""
    resolved_settings = settings or Settings()
    resolved_database = database or Database(resolved_settings.database_url)
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        yield
        await resolved_database.close()

    app = FastAPI(
        title="FabricAssist API",
        version="0.0.0",
        description="Phase 2 backend foundation; business functionality is not implemented.",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.database = resolved_database
    app.state.storage = S3Storage(resolved_settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin for origin in resolved_settings.cors_origins.split(",") if origin],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.add_exception_handler(ApiError, cast(ExceptionHandler, api_error_handler))
    app.add_exception_handler(Exception, cast(ExceptionHandler, unexpected_error_handler))
    app.add_exception_handler(StarletteHTTPException, cast(ExceptionHandler, http_error_handler))
    app.add_exception_handler(
        RequestValidationError, cast(ExceptionHandler, validation_error_handler)
    )

    def get_database(request: Request) -> DatabasePort:
        return request.app.state.database  # type: ignore[no-any-return]

    async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
        database_instance = request.app.state.database
        if not isinstance(database_instance, Database):
            raise ApiError(503, "DEPENDENCY_UNAVAILABLE", "Database sessions are unavailable.")
        async with database_instance.session_factory() as session:
            yield session

    def get_settings(request: Request) -> Settings:
        return request.app.state.settings  # type: ignore[no-any-return]

    def get_storage(request: Request) -> S3Storage:
        return request.app.state.storage  # type: ignore[no-any-return]

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
    app.dependency_overrides[scans.get_session] = get_session
    app.dependency_overrides[scans.get_current_user] = get_current_user
    app.dependency_overrides[scans.get_storage] = get_storage
    app.include_router(auth.router)
    app.include_router(scans.router)

    @app.get("/api/v1/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        """Report process liveness without checking dependencies."""
        return {"status": "ok"}

    @app.get("/api/v1/health/ready", tags=["health"])
    async def ready(
        database_dependency: DatabasePort = Depends(get_database),  # noqa: B008
    ) -> dict[str, str]:
        """Report readiness only when PostgreSQL accepts a safe probe."""
        if not await database_dependency.is_available():
            raise ApiError(503, "DEPENDENCY_UNAVAILABLE", "Service dependencies are unavailable.")
        return {"status": "ok"}

    return app


app = create_app()
