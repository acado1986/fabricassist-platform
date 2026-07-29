from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from fabricassist.application.job_execution import (
    reconcile_unpublished_conversations,
    reconcile_unpublished_operations,
)
from fabricassist.application.jobs import (
    AnalysisJobMessage,
    ConversationJobMessage,
    PermanentJobDispatchError,
    RetryableJobDispatchError,
)
from fabricassist.application.lifecycle import process_object_deletions
from fabricassist.application.object_storage import (
    ObjectNotFoundError,
    PermanentObjectStorageError,
    RetryableObjectStorageError,
)
from fabricassist.infrastructure.jobs.celery import CeleryJobDispatcherAdapter
from fabricassist.infrastructure.jobs.config import (
    CeleryJobDispatcherConfig,
    QStashJobDispatcherConfig,
)
from fabricassist.infrastructure.jobs.qstash import QStashJobDispatcherAdapter
from fabricassist.infrastructure.persistence.models import (
    AnalysisJobOperation,
    ConversationMessage,
    DeletionRequest,
    ObjectDeletionOutbox,
    ScanImage,
)


class Rows:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


@pytest.mark.asyncio
async def test_recovery_preserves_analysis_and_conversation_correlation_ids() -> None:
    analysis = AnalysisJobOperation(
        id=uuid4(),
        scan_id=uuid4(),
        revision_id=uuid4(),
        operation_key="analyse:recover",
        stage="validate_uploaded_images",
        status="queued",
        correlation_id=str(uuid4()),
    )
    conversation = ConversationMessage(
        id=uuid4(),
        tenant_id=uuid4(),
        thread_id=uuid4(),
        scan_id=uuid4(),
        garment_id=uuid4(),
        role="user",
        status="queued",
        text="Synthetic question",
        analysis_revision_id=uuid4(),
        care_result_id=uuid4(),
        dispatch_correlation_id=str(uuid4()),
    )

    class Session:
        def __init__(self, values: list[object]) -> None:
            self.values = values
            self.commits = 0

        async def scalars(self, _statement: object) -> Rows:
            return Rows(self.values)

        async def get(self, _model: object, _identifier: object) -> None:
            return None

        async def commit(self) -> None:
            self.commits += 1

    correlations: list[str] = []

    class Dispatcher:
        async def dispatch_analysis(
            self, message: AnalysisJobMessage, *, correlation_id: str
        ) -> None:
            del message
            correlations.append(correlation_id)

        async def dispatch_conversation(
            self, message: ConversationJobMessage, *, correlation_id: str
        ) -> None:
            del message
            correlations.append(correlation_id)

    dispatcher = Dispatcher()
    assert (
        await reconcile_unpublished_operations(
            session=Session([analysis]),  # type: ignore[arg-type]
            dispatcher=dispatcher,
            correlation_id="fallback",
        )
        == 1
    )
    assert (
        await reconcile_unpublished_conversations(
            session=Session([conversation]),  # type: ignore[arg-type]
            dispatcher=dispatcher,
        )
        == 1
    )
    assert correlations == [analysis.correlation_id, conversation.dispatch_correlation_id]
    assert analysis.published_at is not None
    assert conversation.dispatch_published_at is not None


@pytest.mark.asyncio
async def test_recovery_distinguishes_retryable_and_permanent_publication_errors() -> None:
    retryable = ConversationMessage(
        id=uuid4(),
        tenant_id=uuid4(),
        thread_id=uuid4(),
        scan_id=uuid4(),
        garment_id=uuid4(),
        role="user",
        status="queued",
        text="Retry",
        analysis_revision_id=uuid4(),
        care_result_id=uuid4(),
        dispatch_correlation_id=str(uuid4()),
    )
    permanent = ConversationMessage(
        id=uuid4(),
        tenant_id=uuid4(),
        thread_id=uuid4(),
        scan_id=uuid4(),
        garment_id=uuid4(),
        role="user",
        status="queued",
        text="Reject",
        analysis_revision_id=uuid4(),
        care_result_id=uuid4(),
        dispatch_correlation_id=str(uuid4()),
    )

    class Session:
        def __init__(self, message: ConversationMessage) -> None:
            self.message = message

        async def scalars(self, _statement: object) -> Rows:
            return Rows([self.message])

        async def commit(self) -> None:
            pass

    class Dispatcher:
        def __init__(self, error: Exception) -> None:
            self.error = error

        async def dispatch_analysis(
            self, message: AnalysisJobMessage, *, correlation_id: str
        ) -> None:
            del message, correlation_id

        async def dispatch_conversation(
            self, message: ConversationJobMessage, *, correlation_id: str
        ) -> None:
            del message
            assert correlation_id
            raise self.error

    assert (
        await reconcile_unpublished_conversations(
            session=Session(retryable),  # type: ignore[arg-type]
            dispatcher=Dispatcher(RetryableJobDispatchError("temporary")),
        )
        == 0
    )
    assert retryable.status == "queued"
    assert retryable.dispatch_published_at is None

    assert (
        await reconcile_unpublished_conversations(
            session=Session(permanent),  # type: ignore[arg-type]
            dispatcher=Dispatcher(PermanentJobDispatchError("rejected")),
        )
        == 0
    )
    assert permanent.status == "failed"
    assert permanent.error_code == "JOB_DISPATCH_PERMANENT"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("storage_error", "expected_job_status", "expected_request_status"),
    [
        (None, "completed", "completed"),
        (ObjectNotFoundError("missing"), "completed", "completed"),
        (RetryableObjectStorageError("outage"), "failed", "queued"),
        (PermanentObjectStorageError("rejected"), "failed", "failed"),
    ],
)
async def test_object_deletion_recovery_is_commit_after_io_and_idempotent(
    storage_error: Exception | None,
    expected_job_status: str,
    expected_request_status: str,
) -> None:
    events: list[str] = []
    request = DeletionRequest(
        id=uuid4(),
        tenant_id=uuid4(),
        user_id=uuid4(),
        resource_type="image",
        resource_id=uuid4(),
        status="queued",
    )
    image = ScanImage(
        id=request.resource_id,
        tenant_id=request.tenant_id,
        scan_id=uuid4(),
        role="care_label",
        object_key="private/synthetic.jpg",
        upload_token=uuid4(),
        upload_expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    job = ObjectDeletionOutbox(
        id=uuid4(),
        tenant_id=request.tenant_id,
        deletion_request_id=request.id,
        image_id=image.id,
        object_key=image.object_key,
        status="pending",
        attempts=0,
    )

    class Session:
        def __init__(self) -> None:
            self.scalar_calls = 0

        async def scalars(self, _statement: object) -> Rows:
            self.scalar_calls += 1
            return Rows([job])

        async def get(self, model: object, identifier: object) -> object | None:
            if model is ScanImage and identifier == image.id:
                return image
            if model is DeletionRequest and identifier == request.id:
                return request
            return None

        async def commit(self) -> None:
            events.append("commit")

    class Storage:
        def delete_object(self, key: str) -> None:
            assert key == image.object_key
            assert image.deleted_at is None
            events.append("delete")
            if storage_error is not None:
                raise storage_error

    completed = await process_object_deletions(
        Session(),  # type: ignore[arg-type]
        Storage(),  # type: ignore[arg-type]
        max_attempts=5,
    )

    assert events == ["delete", "commit"]
    assert job.status == expected_job_status
    assert request.status == expected_request_status
    assert completed == (1 if expected_job_status == "completed" else 0)
    assert (image.deleted_at is not None) == (expected_job_status == "completed")


@pytest.mark.asyncio
async def test_celery_and_qstash_translate_native_dispatch_failures() -> None:
    message = AnalysisJobMessage(
        scan_id=uuid4(),
        operation_key="analyse:errors",
        stage="validate_uploaded_images",
        revision_id=uuid4(),
    )

    def fail_celery(_name: str, **_kwargs: object) -> None:
        raise ConnectionError("broker unavailable")

    celery = CeleryJobDispatcherAdapter(
        CeleryJobDispatcherConfig(),
        sender=fail_celery,
    )
    with pytest.raises(RetryableJobDispatchError, match="publication failed"):
        await celery.dispatch_analysis(message, correlation_id=str(uuid4()))

    def reject_celery(_name: str, **_kwargs: object) -> None:
        raise ValueError("invalid synthetic publication")

    celery_rejection = CeleryJobDispatcherAdapter(
        CeleryJobDispatcherConfig(),
        sender=reject_celery,
    )
    with pytest.raises(PermanentJobDispatchError, match="was rejected"):
        await celery_rejection.dispatch_analysis(
            message,
            correlation_id=str(uuid4()),
        )

    async def status(code: int, request: httpx.Request) -> httpx.Response:
        return httpx.Response(code, request=request)

    for code, error_type in (
        (503, RetryableJobDispatchError),
        (400, PermanentJobDispatchError),
    ):
        qstash = QStashJobDispatcherAdapter(
            QStashJobDispatcherConfig(
                token="synthetic-token",
                destination_url="https://api.example.test/internal/jobs/qstash",
                request_timeout_seconds=5,
                delivery_timeout_seconds=75,
            ),
            transport=httpx.MockTransport(lambda request, code=code: status(code, request)),
        )
        with pytest.raises(error_type):
            await qstash.dispatch_analysis(message, correlation_id=str(uuid4()))
