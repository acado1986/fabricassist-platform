"""Stable API error envelope and exception handlers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("fabricassist.api.errors")


class ErrorBody(BaseModel):
    """Public error details that remain stable across API routes."""

    code: str
    message: str
    details: dict[str, Any] | None = None
    correlation_id: str


class ErrorEnvelope(BaseModel):
    """The standard non-success response shape."""

    error: ErrorBody


class ApiError(Exception):
    """An expected API failure that is safe to return to clients."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


def correlation_id_for(request: Request) -> str:
    """Read the middleware-generated identifier, including in exception paths."""
    return str(getattr(request.state, "correlation_id", "unknown"))


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Create a validated public error response without leaking internals."""
    envelope = ErrorEnvelope(
        error=ErrorBody(
            code=code,
            message=message,
            details=details,
            correlation_id=correlation_id_for(request),
        )
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump(exclude_none=True))


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(request, status_code=exc.status_code, code=exc.code, message=exc.message)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        request,
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request validation failed.",
        details={"errors": exc.errors()},
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return error_response(
            request, status_code=404, code="NOT_FOUND", message="Resource not found."
        )
    return error_response(
        request, status_code=exc.status_code, code="HTTP_ERROR", message="Request failed."
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unexpected API error",
        extra={
            "http_method": request.method,
            "http_path": request.url.path,
            "http_status": 500,
            "error_type": type(exc).__name__,
        },
    )
    return error_response(
        request,
        status_code=500,
        code="INTERNAL_ERROR",
        message="An unexpected server error occurred.",
    )
