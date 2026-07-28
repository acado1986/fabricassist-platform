# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from fabricassist.api.main import create_app
from fabricassist.api.routes import internal_jobs
from fabricassist.application.jobs import AnalysisJobMessage
from fabricassist.application.qstash import (
    DeliveryVerificationError,
    parse_delivery,
    verify_qstash_signature,
)
from fabricassist.infrastructure.jobs.factory import create_job_dispatcher
from fabricassist.infrastructure.jobs.qstash import (
    PermanentJobDispatchError,
    QStashJobDispatcher,
    RetryableJobDispatchError,
)
from fabricassist.settings import DeploymentProfile, JobDispatcherType, Settings


def settings() -> Settings:
    return Settings(
        environment="alpha",
        deployment_profile=DeploymentProfile.ALPHA,
        job_dispatcher=JobDispatcherType.QSTASH,
        access_token_secret="x" * 32,
        app_base_url="https://app.example.test",
        api_public_url="https://api.example.test",
        cors_allowed_origins="https://app.example.test",
        database_url="postgresql://alpha:password@db.example.test/fabricassist?sslmode=require",
        database_migration_url=(
            "postgresql://alpha:password@db.example.test/fabricassist?sslmode=require"
        ),
        s3_endpoint_url="https://account.r2.cloudflarestorage.com",
        s3_public_endpoint_url="https://account.r2.cloudflarestorage.com",
        s3_region="auto",
        s3_access_key="synthetic-r2-access-key",
        s3_secret_key="synthetic-r2-secret-key",
        s3_bucket="fabricassist-alpha",
        s3_force_path_style=False,
        qstash_token="test-token-never-log",
        qstash_current_signing_key="current",
        qstash_next_signing_key="next",
        qstash_destination_url="https://api.example.test/internal/jobs/qstash",
        valkey_url="valkey://localhost:6379/15",
    )


def message() -> AnalysisJobMessage:
    return AnalysisJobMessage(
        scan_id=uuid4(),
        operation_key="analyse:test",
        stage="validate_uploaded_images",
        revision_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_qstash_publishes_versioned_identifier_only_message() -> None:
    received: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        received["url"] = str(request.url)
        received["headers"] = dict(request.headers)
        received["json"] = json.loads(request.content)
        return httpx.Response(200, json={"messageId": "synthetic"})

    dispatcher = QStashJobDispatcher(settings(), transport=httpx.MockTransport(handler))
    job = message()
    await dispatcher.dispatch_analysis(job, correlation_id="correlation")
    assert received["json"] == job.model_dump(mode="json")
    assert (
        str(received["url"])
        == "https://qstash.upstash.io/v2/publish/https://api.example.test/internal/jobs/qstash"
    )
    headers = received["headers"]
    assert isinstance(headers, dict) and headers[
        "upstash-deduplication-id"
    ] == dispatcher.deduplication_id(job)


@pytest.mark.asyncio
async def test_qstash_errors_are_safe_and_classified() -> None:
    async def unauthorized(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    with pytest.raises(PermanentJobDispatchError, match="rejected") as permanent_error:
        await QStashJobDispatcher(
            settings(), transport=httpx.MockTransport(unauthorized)
        ).dispatch_analysis(message(), correlation_id="c")
    assert "test-token-never-log" not in str(permanent_error.value)

    async def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    with pytest.raises(RetryableJobDispatchError, match="timed out"):
        await QStashJobDispatcher(
            settings(), transport=httpx.MockTransport(timeout)
        ).dispatch_analysis(message(), correlation_id="c")


def test_message_is_strict_and_deduplication_is_stable() -> None:
    with pytest.raises(ValidationError):
        AnalysisJobMessage.model_validate(
            {
                "scan_id": str(uuid4()),
                "operation_key": "x",
                "stage": "validate_uploaded_images",
                "revision_id": str(uuid4()),
                "extra": "forbidden",
            }
        )
    job = message()
    assert QStashJobDispatcher.deduplication_id(job) == QStashJobDispatcher.deduplication_id(job)
    assert isinstance(create_job_dispatcher(settings()), QStashJobDispatcher)


def signed_delivery(body: bytes, *, key: str = "current", destination: str | None = None) -> str:
    return jwt.encode(
        {
            "sub": destination or settings().qstash_destination_url,
            "body": sha256(body).hexdigest(),
            "exp": datetime.now(UTC) + timedelta(minutes=1),
        },
        key,
        algorithm="HS256",
    )


@pytest.mark.parametrize("key", ["current", "next"])
def test_qstash_verifies_current_and_next_keys_against_raw_body(key: str) -> None:
    body = message().model_dump_json().encode()
    verify_qstash_signature(
        raw_body=body, signature=signed_delivery(body, key=key), settings=settings()
    )


@pytest.mark.parametrize(
    "signature",
    [
        lambda body: signed_delivery(b"other"),
        lambda body: signed_delivery(body, destination="https://wrong.example.test/job"),
        lambda body: jwt.encode(
            {"sub": settings().qstash_destination_url, "body": sha256(body).hexdigest(), "exp": 1},
            "current",
            algorithm="HS256",
        ),
    ],
)
def test_qstash_rejects_modified_destination_or_expired_signature(signature: object) -> None:
    body = message().model_dump_json().encode()
    assert callable(signature)
    with pytest.raises(DeliveryVerificationError):
        verify_qstash_signature(raw_body=body, signature=signature(body), settings=settings())  # type: ignore[operator]


def test_signed_invalid_message_is_non_retryable() -> None:
    with pytest.raises(Exception, match="permanently invalid"):
        parse_delivery(b'{"message_schema_version": 2}')


def test_internal_route_marks_signed_permanent_payload_non_retryable() -> None:
    body = b'{"message_schema_version": 2}'
    app = create_app(settings())

    async def unused_session() -> object:
        return object()

    app.dependency_overrides[internal_jobs.get_session] = unused_session
    with TestClient(app) as client:
        response = client.post(
            "/internal/jobs/qstash",
            content=body,
            headers={"Upstash-Signature": signed_delivery(body)},
        )
    assert response.status_code == 489
    assert response.headers["Upstash-NonRetryable-Error"] == "true"
