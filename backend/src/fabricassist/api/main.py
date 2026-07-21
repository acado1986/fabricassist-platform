"""FastAPI application factory for the Phase 2 backend foundation."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
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
from fabricassist.infrastructure.database import Database, DatabasePort
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
    app.add_middleware(CorrelationIdMiddleware)
    app.add_exception_handler(ApiError, cast(ExceptionHandler, api_error_handler))
    app.add_exception_handler(Exception, cast(ExceptionHandler, unexpected_error_handler))
    app.add_exception_handler(StarletteHTTPException, cast(ExceptionHandler, http_error_handler))
    app.add_exception_handler(
        RequestValidationError, cast(ExceptionHandler, validation_error_handler)
    )

    def get_database(request: Request) -> DatabasePort:
        return request.app.state.database  # type: ignore[no-any-return]

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
