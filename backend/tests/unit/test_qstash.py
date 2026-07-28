from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from fabricassist.application.jobs import AnalysisJobMessage
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
        s3_endpoint_url="https://account.r2.cloudflarestorage.com",
        s3_public_endpoint_url="https://account.r2.cloudflarestorage.com",
        s3_bucket="fabricassist-alpha",
        qstash_token="test-token-never-log",
        qstash_current_signing_key="current",
        qstash_next_signing_key="next",
        qstash_destination_url="https://api.example.test/internal/jobs/qstash",
        valkey_url="",
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
    assert "qstash.upstash.io/v2/publish/https%3A%2F%2Fapi.example.test" in str(received["url"])
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
