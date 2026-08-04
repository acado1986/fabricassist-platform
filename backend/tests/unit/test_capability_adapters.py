from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from uuid import uuid4

import httpx
import pytest

from fabricassist.application.cache import evidence_cache_key
from fabricassist.application.job_orchestration import enqueue_analysis
from fabricassist.application.jobs import AnalysisJobMessage, JobDispatcher
from fabricassist.application.provider import ProviderDescriptor
from fabricassist.application.vision import NormalizedImage
from fabricassist.domain.evidence import ImageRole
from fabricassist.infrastructure.cache.factory import create_hot_cache
from fabricassist.infrastructure.cache.noop import NoOpHotCacheAdapter
from fabricassist.infrastructure.cache.valkey import ValkeyHotCacheAdapter
from fabricassist.infrastructure.concurrency.factory import create_concurrency_gate
from fabricassist.infrastructure.concurrency.noop import NoOpConcurrencyGateAdapter
from fabricassist.infrastructure.jobs.celery import CeleryJobDispatcherAdapter
from fabricassist.infrastructure.jobs.config import (
    CeleryJobDispatcherConfig,
    QStashJobDispatcherConfig,
    QStashVerifierConfig,
)
from fabricassist.infrastructure.jobs.factory import create_job_dispatcher
from fabricassist.infrastructure.jobs.qstash import QStashJobDispatcherAdapter
from fabricassist.infrastructure.persistence.models import (
    AnalysisJobOperation,
    Garment,
    GarmentIdentifier,
    Scan,
)
from fabricassist.infrastructure.product_information.factory import (
    create_product_information_provider,
)
from fabricassist.infrastructure.product_information.mock import (
    MockProductInformationAdapter,
)
from fabricassist.infrastructure.rate_limits.factory import create_rate_limiter
from fabricassist.infrastructure.rate_limits.noop import NoOpRateLimiterAdapter
from fabricassist.infrastructure.rate_limits.valkey import ValkeyRateLimiterAdapter
from fabricassist.infrastructure.storage.factory import create_object_storage
from fabricassist.infrastructure.storage.s3 import (
    S3ObjectStorageAdapter,
    S3ObjectStorageConfig,
)
from fabricassist.infrastructure.vision.providers import (
    GeminiProviderAdapter,
    OpenAIResponsesProviderAdapter,
    create_care_planning_provider,
    create_conversation_provider,
    create_evidence_provider,
)
from fabricassist.infrastructure.vision.providers.mock import MockModelCapabilityAdapter
from fabricassist.settings import (
    ConcurrencyGateBackend,
    HotCacheBackend,
    JobDispatcherType,
    ModelCapabilityProvider,
    RateLimiterBackend,
    Settings,
)
from fabricassist.worker.celery_app import _celery_broker_url  # pyright: ignore[reportPrivateUsage]


def job_message() -> AnalysisJobMessage:
    return AnalysisJobMessage(
        scan_id=uuid4(),
        operation_key="contract:analysis",
        stage="validate_uploaded_images",
        revision_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_celery_and_qstash_share_the_identifier_only_dispatch_contract() -> None:
    message = job_message()
    celery_calls: list[tuple[str, dict[str, object]]] = []

    def send_task(name: str, **kwargs: object) -> None:
        celery_calls.append((name, kwargs))

    celery = CeleryJobDispatcherAdapter(
        CeleryJobDispatcherConfig(),
        sender=send_task,
    )
    qstash_payloads: list[dict[str, object]] = []

    async def publish(request: httpx.Request) -> httpx.Response:
        qstash_payloads.append(json.loads(request.content))
        return httpx.Response(200)

    qstash = QStashJobDispatcherAdapter(
        QStashJobDispatcherConfig(
            token="synthetic-token",
            destination_url="https://api.example.test/internal/jobs/qstash",
            request_timeout_seconds=5,
            delivery_timeout_seconds=75,
        ),
        transport=httpx.MockTransport(publish),
    )

    for adapter in (celery, qstash):
        await adapter.dispatch_analysis(message, correlation_id=str(uuid4()))

    assert celery_calls[0][0] == "fabricassist.execute_analysis_job"
    celery_args = cast(list[str], celery_calls[0][1]["args"])
    assert json.loads(celery_args[0]) == message.model_dump(mode="json")
    assert qstash_payloads == [message.model_dump(mode="json")]
    assert set(qstash_payloads[0]) == {
        "message_schema_version",
        "scan_id",
        "operation_key",
        "stage",
        "revision_id",
    }


def test_capability_factories_select_only_registered_environment_strategies() -> None:
    celery_settings = Settings(
        environment="test",
        job_dispatcher=JobDispatcherType.CELERY,
    )
    assert isinstance(create_job_dispatcher(celery_settings), CeleryJobDispatcherAdapter)
    assert isinstance(create_hot_cache(celery_settings), ValkeyHotCacheAdapter)
    assert isinstance(create_rate_limiter(celery_settings), ValkeyRateLimiterAdapter)

    optional_settings = Settings(
        environment="test",
        job_dispatcher=JobDispatcherType.QSTASH,
        qstash_token="synthetic-token",
        qstash_current_signing_key="c" * 32,
        qstash_next_signing_key="n" * 32,
        qstash_destination_url="https://api.example.test/internal/jobs/qstash",
        hot_cache_backend=HotCacheBackend.NOOP,
        rate_limiter_backend=RateLimiterBackend.NOOP,
        concurrency_gate_backend=ConcurrencyGateBackend.NOOP,
    )
    assert isinstance(create_job_dispatcher(optional_settings), QStashJobDispatcherAdapter)
    assert isinstance(create_hot_cache(optional_settings), NoOpHotCacheAdapter)
    assert isinstance(create_rate_limiter(optional_settings), NoOpRateLimiterAdapter)
    assert isinstance(create_concurrency_gate(optional_settings), NoOpConcurrencyGateAdapter)


def test_model_capabilities_are_selected_independently() -> None:
    configured = Settings(
        environment="test",
        evidence_provider=ModelCapabilityProvider.MOCK,
        care_planner_provider=ModelCapabilityProvider.GEMINI,
        chat_provider=ModelCapabilityProvider.OPENAI_RESPONSES,
        gemini_api_key="synthetic-gemini-key",
        openai_responses_base_url="https://models.example.test/v1",
        openai_responses_api_key="synthetic-openai-key",
        openai_responses_model="synthetic-responses-model",
    )

    evidence = create_evidence_provider(configured)
    planning = create_care_planning_provider(configured)
    conversation = create_conversation_provider(configured)

    assert isinstance(evidence, MockModelCapabilityAdapter)
    assert isinstance(planning, GeminiProviderAdapter)
    assert isinstance(conversation, OpenAIResponsesProviderAdapter)
    assert evidence.descriptor.provider == "mock"
    assert planning.descriptor.provider == "gemini"
    assert conversation.descriptor.provider == "openai_responses"


def test_storage_and_product_factories_construct_registered_capabilities() -> None:
    configured = Settings(
        environment="test",
        s3_access_key="synthetic-access-key",
        s3_secret_key="synthetic-secret-key",
    )

    assert isinstance(create_object_storage(configured), S3ObjectStorageAdapter)
    assert isinstance(
        create_product_information_provider(configured),
        MockProductInformationAdapter,
    )

    storage_config = S3ObjectStorageConfig(
        endpoint_url="https://storage.example.test",
        public_endpoint_url="https://storage.example.test",
        region="auto",
        bucket="private",
        force_path_style=False,
        upload_max_bytes=1024,
        upload_url_minutes=5,
        access_key="credential-must-not-appear",
        secret_key="secret-must-not-appear",
    )
    assert "credential-must-not-appear" not in repr(storage_config)
    assert "secret-must-not-appear" not in repr(storage_config)


def test_evidence_hot_cache_isolated_by_tenant_provider_and_model() -> None:
    image = NormalizedImage(
        image_id=uuid4(),
        jpeg_bytes=b"synthetic",
        sha256="a" * 64,
        width=100,
        height=100,
        role=ImageRole.CARE_LABEL,
    )
    first = evidence_cache_key(
        image,
        tenant_id="tenant-a",
        descriptor=ProviderDescriptor("gemini", "model-a"),
    )
    keys = {
        first,
        evidence_cache_key(
            image,
            tenant_id="tenant-b",
            descriptor=ProviderDescriptor("gemini", "model-a"),
        ),
        evidence_cache_key(
            image,
            tenant_id="tenant-a",
            descriptor=ProviderDescriptor("openai_responses", "model-a"),
        ),
        evidence_cache_key(
            image,
            tenant_id="tenant-a",
            descriptor=ProviderDescriptor("gemini", "model-b"),
        ),
    }

    assert len(keys) == 4
    assert "tenant-a" in first
    assert "gemini" in first
    assert "model-a" in first


def test_celery_broker_normalization_is_transport_local() -> None:
    assert _celery_broker_url("valkey://broker:6379/0") == "redis://broker:6379/0"
    assert _celery_broker_url("amqp://rabbitmq/fabricassist") == ("amqp://rabbitmq/fabricassist")


@pytest.mark.asyncio
async def test_noop_capability_contracts_are_explicit() -> None:
    cache = NoOpHotCacheAdapter()
    assert await cache.get_json("missing") is None
    await cache.set_json("discarded", {"safe": True}, ttl_seconds=60)

    limiter = NoOpRateLimiterAdapter()
    assert await limiter.allowed("bucket", 1, window_seconds=60)
    await limiter.close()

    gate = NoOpConcurrencyGateAdapter()
    async with gate.slot(tenant_id="tenant", operation="analysis"):
        pass


@pytest.mark.asyncio
async def test_valkey_hot_cache_contract_serializes_json_and_uses_ttl() -> None:
    class FakeValkey:
        stored: dict[str, str] = {}
        ttl: int | None = None

        async def get(self, key: str) -> str | None:
            return self.stored.get(key)

        async def set(self, key: str, value: str, *, ex: int) -> None:
            self.stored[key] = value
            self.ttl = ex

    cache = ValkeyHotCacheAdapter("valkey://unused:6379/0")
    fake = FakeValkey()
    cache._client = fake  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001

    await cache.set_json("key", {"safe": True}, ttl_seconds=120)

    assert await cache.get_json("key") == {"safe": True}
    assert fake.ttl == 120


@pytest.mark.asyncio
async def test_job_intent_is_committed_before_external_publication() -> None:
    events: list[str] = []

    class Session:
        added: list[object] = []

        async def scalar(self, _statement: object) -> None:
            return None

        def add(self, value: object) -> None:
            self.added.append(value)

        async def commit(self) -> None:
            events.append("commit")

    class Dispatcher:
        async def dispatch_analysis(
            self,
            message: AnalysisJobMessage,
            *,
            correlation_id: str,
        ) -> None:
            assert message.scan_id == scan.id
            assert correlation_id == "correlation"
            events.append("publish")

    scan = Scan(id=uuid4(), tenant_id=uuid4(), status="draft", requested_language="en")
    session = Session()
    operation = await enqueue_analysis(
        session=session,  # type: ignore[arg-type]
        scan=scan,
        operation_key="analyse:committed-first",
        correlation_id="correlation",
        dispatcher=cast(JobDispatcher, Dispatcher()),
        settings=Settings(),
    )

    assert events == ["commit", "publish", "commit"]
    assert isinstance(operation, AnalysisJobOperation)
    assert operation.published_at is not None
    assert scan.garment_id is not None
    garments = [item for item in session.added if isinstance(item, Garment)]
    identifiers = [item for item in session.added if isinstance(item, GarmentIdentifier)]
    assert len(garments) == 1
    assert len(identifiers) == 1
    assert identifiers[0].garment_id == scan.garment_id


@pytest.mark.asyncio
async def test_committed_unpublished_intent_is_republished_on_retry() -> None:
    class Session:
        def __init__(self) -> None:
            self.operation: AnalysisJobOperation | None = None
            self.commits = 0

        async def scalar(self, _statement: object) -> AnalysisJobOperation | None:
            return self.operation

        def add(self, value: object) -> None:
            if isinstance(value, AnalysisJobOperation):
                self.operation = value

        async def commit(self) -> None:
            self.commits += 1

    class Failing:
        async def dispatch_analysis(
            self,
            message: AnalysisJobMessage,
            *,
            correlation_id: str,
        ) -> None:
            del message, correlation_id
            raise RuntimeError("synthetic publication failure")

    published: list[AnalysisJobMessage] = []

    class Succeeding:
        async def dispatch_analysis(
            self,
            message: AnalysisJobMessage,
            *,
            correlation_id: str,
        ) -> None:
            assert correlation_id == "correlation"
            published.append(message)

    scan = Scan(id=uuid4(), tenant_id=uuid4(), status="draft", requested_language="en")
    session = Session()
    with pytest.raises(RuntimeError, match="publication failure"):
        await enqueue_analysis(
            session=session,  # type: ignore[arg-type]
            scan=scan,
            operation_key="analyse:recover",
            correlation_id="correlation",
            dispatcher=cast(JobDispatcher, Failing()),
            settings=Settings(),
        )
    assert session.operation is not None
    assert session.operation.published_at is None
    assert session.commits == 1

    recovered = await enqueue_analysis(
        session=session,  # type: ignore[arg-type]
        scan=scan,
        operation_key="analyse:recover",
        correlation_id="new-request-correlation",
        dispatcher=cast(JobDispatcher, Succeeding()),
        settings=Settings(),
    )

    assert len(published) == 1
    assert published[0].operation_key == recovered.operation_key
    assert recovered.published_at is not None
    assert recovered.correlation_id == "correlation"


def test_adapter_credentials_are_redacted_from_configuration_representations() -> None:
    token = "credential-must-not-appear"
    outbound = QStashJobDispatcherConfig(
        token=token,
        destination_url="https://api.example.test/internal/jobs/qstash",
        request_timeout_seconds=5,
        delivery_timeout_seconds=75,
    )
    inbound = QStashVerifierConfig(
        current_signing_key=token,
        next_signing_key=f"next-{token}",
        destination_url="https://api.example.test/internal/jobs/qstash",
    )
    configured = Settings(
        qstash_token=token,
        qstash_current_signing_key=token,
        database_url=f"postgresql://user:{token}@database/fabricassist",
        valkey_url=f"redis://user:{token}@cache/0",
        celery_broker_url=f"redis://user:{token}@broker/0",
    )

    assert token not in repr(outbound)
    assert token not in repr(inbound)
    assert token not in repr(configured)


def test_routes_do_not_select_or_call_job_transports() -> None:
    routes = Path(__file__).resolve().parents[2] / "src/fabricassist/api/routes"
    source = "\n".join(path.read_text() for path in routes.glob("*.py"))
    assert "celery_app.send_task" not in source
    scan_source = (routes / "scans.py").read_text()
    assert "JobDispatcherType" not in scan_source
    assert "QSTASH" not in scan_source
    assert "CELERY" not in scan_source
