from __future__ import annotations

import json
import logging
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from redis.exceptions import RedisError

from fabricassist.api.logging import JsonFormatter
from fabricassist.api.main import create_app
from fabricassist.api.middleware import metric_route
from fabricassist.application.limits import (
    ConcurrencyLimitExceeded,
    LimitBackendUnavailable,
)
from fabricassist.infrastructure.concurrency.valkey import ValkeyConcurrencyGateAdapter
from fabricassist.infrastructure.rate_limits.valkey import ValkeyRateLimiterAdapter
from fabricassist.infrastructure.storage.factory import create_object_storage
from fabricassist.settings import (
    ConcurrencyGateBackend,
    RateLimiterBackend,
    Settings,
)


class AvailableDatabase:
    async def is_available(self) -> bool:
        return True

    async def close(self) -> None:
        return None


class FakeRedis:
    def __init__(self, *, counts: list[int] | None = None, acquire: int = 1) -> None:
        self.counts = counts or [1]
        self.acquire = acquire
        self.expired: list[tuple[str, int]] = []
        self.removed: list[tuple[str, str]] = []
        self.eval_calls: list[tuple[object, ...]] = []
        self.closed = False

    async def incr(self, _key: str) -> int:
        return self.counts.pop(0)

    async def expire(self, key: str, seconds: int) -> None:
        self.expired.append((key, seconds))

    async def eval(self, *_args: object) -> int:
        self.eval_calls.append(_args)
        return self.acquire

    async def zrem(self, key: str, token: str) -> None:
        self.removed.append((key, token))

    async def aclose(self) -> None:
        self.closed = True


def production_settings(**updates: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "database_url": "postgresql://app:secret@db.internal/fabricassist?sslmode=require",
        "access_token_secret": "a" * 64,
        "app_base_url": "https://app.example.test",
        "api_public_url": "https://api.example.test",
        "cors_allowed_origins": "https://app.example.test",
        "s3_access_key": "staging-workload",
        "s3_secret_key": "b" * 48,
        "s3_bucket": "fabricassist-staging-private",
        "s3_endpoint_url": "https://s3.eu-west-1.amazonaws.com",
        "s3_public_endpoint_url": "https://s3.eu-west-1.amazonaws.com",
        "valkey_url": "rediss://cache.internal:6379/0",
        "celery_broker_url": "rediss://broker.internal:6379/0",
        "rate_limit_enabled": True,
        "rate_limit_fail_open": False,
        "metrics_access_token": "c" * 32,
        "vision_debug_logging": False,
    }
    values.update(updates)
    return Settings(**values)  # type: ignore[arg-type]


def test_production_settings_accept_only_explicit_secure_network_policy() -> None:
    settings = production_settings()
    assert settings.environment == "production"

    with pytest.raises(ValidationError, match="explicit HTTPS origins"):
        production_settings(cors_allowed_origins="*")
    with pytest.raises(ValidationError, match="fail closed"):
        production_settings(rate_limit_fail_open=True)
    with pytest.raises(ValidationError, match="METRICS_ACCESS_TOKEN"):
        production_settings(metrics_access_token="short")
    with pytest.raises(ValidationError, match="RATE_LIMITER_BACKEND=noop"):
        production_settings(rate_limiter_backend=RateLimiterBackend.NOOP)
    with pytest.raises(ValidationError, match="CONCURRENCY_GATE_BACKEND=noop"):
        production_settings(concurrency_gate_backend=ConcurrencyGateBackend.NOOP)


def test_production_storage_can_use_workload_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    client_calls: list[dict[str, object]] = []

    def client_factory(_service: str, **kwargs: object) -> object:
        client_calls.append(kwargs)
        return object()

    monkeypatch.setattr("fabricassist.infrastructure.storage.s3.boto3.client", client_factory)
    create_object_storage(production_settings(s3_access_key="", s3_secret_key=""))

    assert len(client_calls) == 2
    assert all("aws_access_key_id" not in call for call in client_calls)
    assert all("aws_secret_access_key" not in call for call in client_calls)


def test_s3_storage_uses_r2_region_and_virtual_addressing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_calls: list[dict[str, object]] = []

    def client_factory(_service: str, **kwargs: object) -> object:
        client_calls.append(kwargs)
        return object()

    monkeypatch.setattr("fabricassist.infrastructure.storage.s3.boto3.client", client_factory)
    create_object_storage(
        Settings(
            environment="test",
            s3_endpoint_url="https://account-id.r2.cloudflarestorage.com",
            s3_public_endpoint_url="https://account-id.r2.cloudflarestorage.com",
            s3_region="auto",
            s3_bucket="fabricassist-alpha",
            s3_access_key="synthetic-r2-key",
            s3_secret_key="synthetic-r2-secret",
            s3_force_path_style=False,
        )
    )

    assert len(client_calls) == 2
    assert all(call["region_name"] == "auto" for call in client_calls)
    assert all(
        call["endpoint_url"] == "https://account-id.r2.cloudflarestorage.com"
        for call in client_calls
    )
    assert all(
        cast(dict[str, str], cast(Any, call["config"]).s3)["addressing_style"] == "virtual"
        for call in client_calls
    )


def test_api_applies_security_headers_and_supports_actual_cors_methods() -> None:
    with TestClient(create_app(Settings(environment="test"), AvailableDatabase())) as client:
        response = client.get("/api/v1/health/live")
        preflight = client.options(
            "/api/v1/scans/00000000-0000-0000-0000-000000000000",
            headers={
                "Origin": "http://localhost:8081",
                "Access-Control-Request-Method": "DELETE",
                "Access-Control-Request-Headers": "authorization,x-correlation-id",
            },
        )

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["content-security-policy"].startswith("default-src")
    assert preflight.status_code == 200
    assert "DELETE" in preflight.headers["access-control-allow-methods"]


def test_metrics_are_bearer_protected_and_use_bounded_route_labels() -> None:
    settings = Settings(environment="test", metrics_access_token="m" * 32)
    with TestClient(create_app(settings, AvailableDatabase())) as client:
        denied = client.get("/api/v1/metrics")
        allowed = client.get("/api/v1/metrics", headers={"Authorization": f"Bearer {'m' * 32}"})

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert "fabricassist_http_requests_total" in allowed.text
    assert (
        metric_route("/api/v1/scans/92e58c17-6a97-42f5-8f87-4dd85f1d8aad/result")
        == "/api/v1/scans/{id}/result"
    )


@pytest.mark.asyncio
async def test_rate_limiter_sets_window_and_rejects_over_limit() -> None:
    limiter = ValkeyRateLimiterAdapter("valkey://unused:6379/0")
    fake = FakeRedis(counts=[1, 3])
    limiter._client = fake  # type: ignore[assignment]  # noqa: SLF001

    assert await limiter.allowed("tenant", 2, window_seconds=60)
    assert not await limiter.allowed("tenant", 2, window_seconds=60)
    assert fake.expired


@pytest.mark.asyncio
async def test_distributed_concurrency_slot_releases_both_leases() -> None:
    gate = ValkeyConcurrencyGateAdapter(
        url="valkey://unused:6379/0",
        global_limit=8,
        tenant_limit=2,
        lease_seconds=300,
    )
    fake = FakeRedis(acquire=1)
    gate._client = fake  # type: ignore[assignment]  # noqa: SLF001

    async with gate.slot(tenant_id="tenant", operation="analysis"):
        pass

    assert len(fake.removed) == 2
    assert "ZREMRANGEBYSCORE" in str(fake.eval_calls[0][0])
    assert cast(int, fake.eval_calls[0][5]) - cast(int, fake.eval_calls[0][4]) == 300
    assert fake.closed


@pytest.mark.asyncio
async def test_distributed_concurrency_rejects_when_full() -> None:
    gate = ValkeyConcurrencyGateAdapter(
        url="valkey://unused:6379/0",
        global_limit=8,
        tenant_limit=2,
        lease_seconds=300,
    )
    fake = FakeRedis(acquire=0)
    gate._client = fake  # type: ignore[assignment]  # noqa: SLF001

    with pytest.raises(ConcurrencyLimitExceeded):
        async with gate.slot(tenant_id="tenant", operation="analysis"):
            pass
    assert fake.closed


@pytest.mark.asyncio
async def test_limit_adapters_translate_backend_failures() -> None:
    class FailingRedis(FakeRedis):
        async def incr(self, _key: str) -> int:
            raise RedisError("synthetic backend failure")

        async def eval(self, *_args: object) -> int:
            raise RedisError("synthetic backend failure")

    limiter = ValkeyRateLimiterAdapter("valkey://unused:6379/0")
    limiter._client = FailingRedis()  # type: ignore[assignment]  # noqa: SLF001
    with pytest.raises(LimitBackendUnavailable):
        await limiter.allowed("tenant", 2, window_seconds=60)

    gate = ValkeyConcurrencyGateAdapter(
        url="valkey://unused:6379/0",
        global_limit=8,
        tenant_limit=2,
        lease_seconds=300,
    )
    failing_gate_client = FailingRedis()
    gate._client = failing_gate_client  # type: ignore[assignment]  # noqa: SLF001
    with pytest.raises(LimitBackendUnavailable):
        async with gate.slot(tenant_id="tenant", operation="analysis"):
            pass
    assert failing_gate_client.closed


def test_json_logging_redacts_common_secret_shapes() -> None:
    record = logging.LogRecord(
        "fabricassist.test",
        logging.INFO,
        __file__,
        1,
        "authorization: Bearer-secret password=cleartext",
        (),
        None,
    )
    payload = json.loads(JsonFormatter().format(record))

    assert "Bearer-secret" not in payload["message"]
    assert "cleartext" not in payload["message"]
    assert payload["message"].count("[REDACTED]") == 2
