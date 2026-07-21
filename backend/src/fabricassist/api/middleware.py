"""HTTP middleware shared by the foundation endpoints."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from fabricassist.api.logging import correlation_id_context

logger = logging.getLogger("fabricassist.http")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Propagate a valid client correlation ID or generate a fresh UUID."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("X-Correlation-ID")
        try:
            correlation_id = str(UUID(incoming)) if incoming else str(uuid4())
        except ValueError:
            correlation_id = str(uuid4())

        request.state.correlation_id = correlation_id
        token = correlation_id_context.set(correlation_id)
        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            logger.info(
                "request_completed",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status": response.status_code,
                },
            )
            return response
        finally:
            correlation_id_context.reset(token)
