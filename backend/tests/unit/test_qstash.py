# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false
from __future__ import annotations

import base64
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
from fabricassist.application.job_execution import (
    AnalysisExecutionError,
    StageResult,
    TemporaryJobError,
    execute_checkpoint,
)
from fabricassist.application.jobs import AnalysisJobMessage
from fabricassist.application.policies import JobExecutionPolicy
from fabricassist.infrastructure.concurrency.noop import NoOpConcurrencyGateAdapter
from fabricassist.infrastructure.jobs.config import QStashJobDispatcherConfig, QStashVerifierConfig
from fabricassist.infrastructure.jobs.factory import create_job_dispatcher
from fabricassist.infrastructure.jobs.qstash import (
    PermanentJobDispatchError,
    QStashJobDispatcherAdapter,
    RetryableJobDispatchError,
)
from fabricassist.infrastructure.jobs.qstash_inbound import (
    DeliveryVerificationError,
    QStashDeliveryVerifier,
)
from fabricassist.settings import (
    ConcurrencyGateBackend,
    DeploymentProfile,
    HotCacheBackend,
    JobDispatcherType,
    RateLimiterBackend,
    Settings,
)

CURRENT_SIGNING_KEY = "current-signing-key-for-tests-0001"
NEXT_SIGNING_KEY = "next-signing-key-for-tests-000002"


def settings() -> Settings:
    return Settings(
        environment="alpha",
        deployment_profile=DeploymentProfile.ALPHA,
        job_dispatcher=JobDispatcherType.QSTASH,
        hot_cache_backend=HotCacheBackend.NOOP,
        rate_limiter_backend=RateLimiterBackend.NOOP,
        concurrency_gate_backend=ConcurrencyGateBackend.NOOP,
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
        qstash_current_signing_key=CURRENT_SIGNING_KEY,
        qstash_next_signing_key=NEXT_SIGNING_KEY,
        qstash_destination_url="https://api.example.test/internal/jobs/qstash",
        valkey_url="valkey://localhost:6379/15",
    )


def qstash_dispatcher(
    configured: Settings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> QStashJobDispatcherAdapter:
    return QStashJobDispatcherAdapter(
        QStashJobDispatcherConfig(
            token=configured.qstash_token,
            destination_url=configured.qstash_destination_url,
            request_timeout_seconds=30,
            delivery_timeout_seconds=configured.job_stage_budget_seconds,
        ),
        transport=transport,
    )


def qstash_verifier() -> QStashDeliveryVerifier:
    configured = settings()
    return QStashDeliveryVerifier(
        QStashVerifierConfig(
            current_signing_key=configured.qstash_current_signing_key,
            next_signing_key=configured.qstash_next_signing_key,
            destination_url=configured.qstash_destination_url,
        )
    )


def message() -> AnalysisJobMessage:
    return AnalysisJobMessage(
        scan_id=uuid4(),
        operation_key="analyse:test",
        stage="validate_uploaded_images",
        revision_id=uuid4(),
    )


class CheckpointSession:
    def __init__(self, responses: list[object | None], scan: object) -> None:
        self.responses = responses
        self.scan = scan
        self.added: list[object] = []
        self.commit_count = 0
        self.scalar_statements: list[object] = []

    async def scalar(self, statement: object) -> object | None:
        self.scalar_statements.append(statement)
        return self.responses.pop(0)

    async def get(
        self, _model: object, _identifier: object, *, with_for_update: bool = False
    ) -> object:
        assert with_for_update
        return self.scan

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commit_count += 1


@pytest.mark.asyncio
async def test_checkpoint_persists_and_recovers_unpublished_continuation() -> None:
    from fabricassist.infrastructure.persistence.models import AnalysisJobOperation, Scan

    job = message()
    scan = Scan(id=job.scan_id, tenant_id=uuid4(), status="queued", requested_language="en")
    operation = AnalysisJobOperation(
        id=uuid4(),
        scan_id=job.scan_id,
        revision_id=job.revision_id,
        operation_key=job.operation_key,
        stage=job.stage,
    )
    session = CheckpointSession([operation, uuid4()], scan)

    first = await execute_checkpoint(
        session=session,  # type: ignore[arg-type]
        message=job,
        execution_policy=JobExecutionPolicy(stage_budget_seconds=75),
    )

    continuation = next(value for value in session.added if isinstance(value, AnalysisJobOperation))
    assert first.outcome is StageResult.COMPLETE
    assert first.continuation is not None
    assert first.continuation.stage == "execute_analysis"
    assert operation.status == "completed"
    assert continuation.stage == "execute_analysis"

    session.responses.extend([operation, continuation])
    recovered = await execute_checkpoint(
        session=session,  # type: ignore[arg-type]
        message=job,
        execution_policy=JobExecutionPolicy(stage_budget_seconds=75),
    )
    assert recovered.continuation == first.continuation

    continuation.published_at = datetime.now(UTC)
    session.responses.extend([operation, None])
    duplicate = await execute_checkpoint(
        session=session,  # type: ignore[arg-type]
        message=job,
        execution_policy=JobExecutionPolicy(stage_budget_seconds=75),
    )
    assert duplicate.outcome is StageResult.COMPLETE
    assert duplicate.continuation is None


@pytest.mark.asyncio
async def test_execute_analysis_stage_uses_v2_workflow_only() -> None:
    from fabricassist.infrastructure.persistence.models import AnalysisJobOperation, Scan

    initial = message()
    job = initial.model_copy(update={"stage": "execute_analysis"})
    scan = Scan(id=job.scan_id, tenant_id=uuid4(), status="queued", requested_language="en")
    operation = AnalysisJobOperation(
        id=uuid4(),
        scan_id=job.scan_id,
        revision_id=job.revision_id,
        operation_key=job.operation_key,
        stage=job.stage,
    )
    session = CheckpointSession([operation], scan)
    calls: list[object] = []

    class RecordingWorkflow:
        async def execute(self, request: object) -> None:
            calls.append(request)

    result = await execute_checkpoint(
        session=session,  # type: ignore[arg-type]
        message=job,
        execution_policy=JobExecutionPolicy(stage_budget_seconds=75),
        garment_analysis_workflow=RecordingWorkflow(),  # type: ignore[arg-type]
        concurrency_gate=NoOpConcurrencyGateAdapter(),
    )

    assert result.outcome is StageResult.COMPLETE
    assert result.continuation is None
    assert len(calls) == 1
    assert calls[0].reference.revision_id == job.revision_id  # type: ignore[union-attr]
    assert operation.status == "completed"
    assert session.commit_count == 2
    assert "analysis_job_operations.stage =" in str(session.scalar_statements[0])


@pytest.mark.asyncio
async def test_execute_analysis_stage_records_a_safe_terminal_error() -> None:
    from fabricassist.infrastructure.persistence.models import AnalysisJobOperation, Scan

    initial = message()
    job = initial.model_copy(update={"stage": "execute_analysis"})
    scan = Scan(id=job.scan_id, tenant_id=uuid4(), status="queued", requested_language="en")
    operation = AnalysisJobOperation(
        id=uuid4(),
        scan_id=job.scan_id,
        revision_id=job.revision_id,
        operation_key=job.operation_key,
        stage=job.stage,
    )
    session = CheckpointSession([operation], scan)

    class FailingWorkflow:
        async def execute(self, _request: object) -> None:
            raise RuntimeError("private provider payload must never reach client state")

    async def fail_analysis(**_kwargs: object) -> None:
        raise RuntimeError("private provider payload must never reach client state")

    with pytest.raises(AnalysisExecutionError) as raised:
        await execute_checkpoint(
            session=session,  # type: ignore[arg-type]
            message=job,
            execution_policy=JobExecutionPolicy(stage_budget_seconds=75),
            garment_analysis_workflow=FailingWorkflow(),  # type: ignore[arg-type]
            concurrency_gate=NoOpConcurrencyGateAdapter(),
        )

    assert raised.value.code == "ANALYSIS_EXECUTION_ERROR"
    assert raised.value.cause_type == "RuntimeError"
    assert scan.status == "failed"
    assert scan.analysis_stage == "failed"
    assert scan.analysis_error_code == "ANALYSIS_EXECUTION_ERROR"
    assert scan.progress_percent == 100
    assert operation.status == "failed"
    assert operation.lease_expires_at is None


@pytest.mark.asyncio
async def test_execute_analysis_stage_releases_lease_before_a_timeout_retry() -> None:
    from fabricassist.infrastructure.persistence.models import AnalysisJobOperation, Scan

    initial = message()
    job = initial.model_copy(update={"stage": "execute_analysis"})
    scan = Scan(id=job.scan_id, tenant_id=uuid4(), status="queued", requested_language="en")
    operation = AnalysisJobOperation(
        id=uuid4(),
        scan_id=job.scan_id,
        revision_id=job.revision_id,
        operation_key=job.operation_key,
        stage=job.stage,
    )
    session = CheckpointSession([operation], scan)

    class TimeoutWorkflow:
        async def execute(self, _request: object) -> None:
            raise TimeoutError("synthetic outage")

    with pytest.raises(TemporaryJobError):
        await execute_checkpoint(
            session=session,  # type: ignore[arg-type]
            message=job,
            execution_policy=JobExecutionPolicy(stage_budget_seconds=75),
            garment_analysis_workflow=TimeoutWorkflow(),  # type: ignore[arg-type]
            concurrency_gate=NoOpConcurrencyGateAdapter(),
        )

    assert operation.status == "queued"
    assert operation.lease_expires_at is None
    assert scan.status == "queued"
    assert scan.analysis_stage == "execute_analysis"


def test_internal_route_retries_when_continuation_publication_fails() -> None:
    from fabricassist.infrastructure.persistence.models import AnalysisJobOperation, Scan

    job = message()
    scan = Scan(id=job.scan_id, tenant_id=uuid4(), status="queued", requested_language="en")
    operation = AnalysisJobOperation(
        id=uuid4(),
        scan_id=job.scan_id,
        revision_id=job.revision_id,
        operation_key=job.operation_key,
        stage=job.stage,
    )
    continuation = AnalysisJobOperation(
        id=uuid4(),
        scan_id=job.scan_id,
        revision_id=job.revision_id,
        operation_key=job.operation_key,
        stage="execute_analysis",
        correlation_id=str(uuid4()),
    )
    session = CheckpointSession([operation, uuid4(), continuation], scan)

    class FailingDispatcher:
        async def dispatch_analysis(
            self, _message: AnalysisJobMessage, *, correlation_id: str
        ) -> None:
            assert correlation_id
            raise RetryableJobDispatchError("synthetic failure")

    body = job.model_dump_json().encode()
    app = create_app(settings())
    app.dependency_overrides[internal_jobs.get_session] = lambda: session
    app.dependency_overrides[internal_jobs.get_job_dispatcher] = lambda: FailingDispatcher()

    with TestClient(app) as client:
        response = client.post(
            "/internal/jobs/qstash",
            content=body,
            headers={"Upstash-Signature": signed_delivery(body)},
        )

    continuation = next(
        value
        for value in session.added
        if isinstance(value, AnalysisJobOperation) and value.stage == "execute_analysis"
    )
    assert response.status_code == 503
    assert operation.status == "completed"
    assert continuation.published_at is None


@pytest.mark.asyncio
async def test_qstash_publishes_versioned_identifier_only_message() -> None:
    received: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        received["url"] = str(request.url)
        received["headers"] = dict(request.headers)
        received["json"] = json.loads(request.content)
        return httpx.Response(200, json={"messageId": "synthetic"})

    dispatcher = qstash_dispatcher(settings(), transport=httpx.MockTransport(handler))
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
        await qstash_dispatcher(
            settings(), transport=httpx.MockTransport(unauthorized)
        ).dispatch_analysis(message(), correlation_id="c")
    assert "test-token-never-log" not in str(permanent_error.value)

    async def timeout(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    with pytest.raises(RetryableJobDispatchError, match="timed out"):
        await qstash_dispatcher(
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
    assert QStashJobDispatcherAdapter.deduplication_id(
        job
    ) == QStashJobDispatcherAdapter.deduplication_id(job)
    assert isinstance(create_job_dispatcher(settings()), QStashJobDispatcherAdapter)


def signed_delivery(
    body: bytes,
    *,
    key: str = CURRENT_SIGNING_KEY,
    destination: str | None = None,
) -> str:
    return jwt.encode(
        {
            "iss": "Upstash",
            "sub": destination or settings().qstash_destination_url,
            "body": base64.urlsafe_b64encode(sha256(body).digest()).decode(),
            "exp": datetime.now(UTC) + timedelta(minutes=1),
            "nbf": datetime.now(UTC) - timedelta(seconds=1),
        },
        key,
        algorithm="HS256",
    )


@pytest.mark.parametrize("key", [CURRENT_SIGNING_KEY, NEXT_SIGNING_KEY])
def test_qstash_verifies_current_and_next_keys_against_raw_body(key: str) -> None:
    body = message().model_dump_json().encode()
    qstash_verifier().verify(raw_body=body, signature=signed_delivery(body, key=key))


@pytest.mark.parametrize(
    "signature",
    [
        lambda body: signed_delivery(b"other"),
        lambda body: signed_delivery(body, destination="https://wrong.example.test/job"),
        lambda body: jwt.encode(
            {
                "iss": "Not-Upstash",
                "sub": settings().qstash_destination_url,
                "body": base64.urlsafe_b64encode(sha256(body).digest()).decode(),
                "exp": datetime.now(UTC) + timedelta(minutes=1),
                "nbf": datetime.now(UTC) - timedelta(seconds=1),
            },
            CURRENT_SIGNING_KEY,
            algorithm="HS256",
        ),
    ],
)
def test_qstash_rejects_modified_destination_or_expired_signature(signature: object) -> None:
    body = message().model_dump_json().encode()
    assert callable(signature)
    with pytest.raises(DeliveryVerificationError):
        qstash_verifier().verify(raw_body=body, signature=signature(body))  # type: ignore[operator]


def test_signed_invalid_message_is_non_retryable() -> None:
    with pytest.raises(Exception, match="permanently invalid"):
        qstash_verifier().parse(b'{"message_schema_version": 2}')


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
