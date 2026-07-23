"""HTTP middleware shared by the foundation endpoints."""

from __future__ import annotations

import logging
from hashlib import sha256
from time import perf_counter
from uuid import UUID, uuid4

import jwt
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from fabricassist.api.logging import correlation_id_context
from fabricassist.infrastructure.limits import LimitBackendUnavailable, ValkeyRateLimiter
from fabricassist.infrastructure.telemetry import (
    HTTP_DURATION,
    HTTP_REQUESTS,
    RATE_LIMITED,
)
from fabricassist.settings import Settings

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
        started = perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            duration = perf_counter() - started
            logger.info(
                "request_completed",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status": response.status_code,
                },
            )
            route = metric_route(request.url.path)
            HTTP_REQUESTS.labels(
                method=request.method, route=route, status=str(response.status_code)
            ).inc()
            HTTP_DURATION.labels(method=request.method, route=route).observe(duration)
            return response
        finally:
            correlation_id_context.reset(token)


def metric_route(path: str) -> str:
    """Bound metric cardinality by replacing UUID-looking path components."""
    return "/".join("{id}" if _is_uuid(part) else part for part in path.split("/"))


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply explicit API security headers without relying on an edge proxy."""

    def __init__(self, app: object, settings: Settings) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._settings = settings

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if request.url.path not in {"/api/v1/health/live", "/api/v1/health/ready"}:
            response.headers["Cache-Control"] = "no-store"
        if self._settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self._settings.security_hsts_seconds}; includeSubDomains"
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce shared global and abuse-sensitive endpoint limits in Valkey."""

    def __init__(
        self,
        app: object,
        settings: Settings,
        limiter: ValkeyRateLimiter | None = None,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._settings = settings
        self._limiter = limiter or ValkeyRateLimiter(settings.valkey_url)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if (
            not self._settings.rate_limit_enabled
            or self._settings.environment == "test"
            or request.method in {"GET", "HEAD", "OPTIONS"}
        ):
            return await call_next(request)
        subject = self._subject(request)
        policies = [
            ("global", self._settings.rate_limit_global_per_minute),
            self._endpoint_policy(request),
        ]
        try:
            for policy, limit in policies:
                bucket = "global" if policy == "global" else f"{policy}:{subject}"
                if not await self._limiter.allowed(bucket, limit):
                    RATE_LIMITED.labels(policy=policy).inc()
                    return self._error(request, 429, "RATE_LIMITED", "Request limit exceeded.")
        except LimitBackendUnavailable:
            if not self._settings.rate_limit_fail_open:
                return self._error(
                    request,
                    503,
                    "RATE_LIMIT_UNAVAILABLE",
                    "Request protection is temporarily unavailable.",
                )
        return await call_next(request)

    def _endpoint_policy(self, request: Request) -> tuple[str, int]:
        path = request.url.path
        if path.startswith("/api/v1/auth/"):
            return "auth", self._settings.rate_limit_auth_per_minute
        if path.endswith("/analyse"):
            return "analysis", self._settings.rate_limit_analysis_per_minute
        if path.endswith("/messages"):
            return "chat", self._settings.rate_limit_chat_per_minute
        return "mutation", self._settings.rate_limit_global_per_minute

    def _subject(self, request: Request) -> str:
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            try:
                claims = jwt.decode(  # pyright: ignore[reportUnknownMemberType]
                    authorization.removeprefix("Bearer "),
                    self._settings.access_token_secret,
                    algorithms=["HS256"],
                )
                tenant_id = str(claims.get("tenant_id", ""))
                if tenant_id:
                    return "tenant-" + sha256(tenant_id.encode()).hexdigest()[:24]
            except jwt.InvalidTokenError:
                pass
        client = request.client.host if request.client is not None else "unknown"
        return "client-" + sha256(client.encode()).hexdigest()[:24]

    @staticmethod
    def _error(request: Request, status: int, code: str, message: str) -> JSONResponse:
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "details": {},
                    "correlation_id": str(getattr(request.state, "correlation_id", "unknown")),
                }
            },
            headers={"Retry-After": "60"},
        )
