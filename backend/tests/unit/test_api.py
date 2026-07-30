from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from fabricassist.api.errors import unexpected_error_handler
from fabricassist.api.main import create_app
from fabricassist.api.routes.scans import CreateScanRequest, ImageRequest
from fabricassist.application.jobs import JobDispatcher
from fabricassist.application.policies import UploadPolicy
from fabricassist.settings import Settings


class AvailableDatabase:
    closed = False

    async def is_available(self) -> bool:
        return True

    async def close(self) -> None:
        self.closed = True


class UnavailableDatabase(AvailableDatabase):
    async def is_available(self) -> bool:
        return False


def test_liveness_is_independent_of_database() -> None:
    with TestClient(create_app(Settings(environment="test"), UnavailableDatabase())) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-FabricAssist-Revision"] == "local"


def test_readiness_succeeds_when_database_is_available() -> None:
    with TestClient(create_app(Settings(environment="test"), AvailableDatabase())) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_uses_stable_error_envelope_when_database_is_unavailable() -> None:
    with TestClient(create_app(Settings(environment="test"), UnavailableDatabase())) as client:
        response = client.get("/api/v1/health/ready")

    body = response.json()
    assert response.status_code == 503
    assert body["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert body["error"]["correlation_id"] == response.headers["X-Correlation-ID"]


def test_bootstrap_probes_only_the_database_needed_for_login() -> None:
    with TestClient(create_app(Settings(environment="test"), AvailableDatabase())) as client:
        response = client.get("/api/v1/bootstrap")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_bootstrap_uses_stable_error_envelope_when_database_is_unavailable() -> None:
    with TestClient(create_app(Settings(environment="test"), UnavailableDatabase())) as client:
        response = client.get("/api/v1/bootstrap")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"


def test_not_found_uses_stable_error_envelope() -> None:
    with TestClient(create_app(Settings(environment="test"), AvailableDatabase())) as client:
        response = client.get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_correlation_id_is_propagated() -> None:
    correlation_id = "6b5f4e09-57ef-4592-ae08-b1a1c889209f"
    with TestClient(create_app(Settings(environment="test"), AvailableDatabase())) as client:
        response = client.get("/api/v1/health/live", headers={"X-Correlation-ID": correlation_id})

    assert response.headers["X-Correlation-ID"] == correlation_id


@pytest.mark.asyncio
async def test_unexpected_error_is_logged_without_exception_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logged: list[tuple[str, dict[str, object]]] = []

    def capture(message: str, *, extra: dict[str, object]) -> None:
        logged.append((message, extra))

    monkeypatch.setattr("fabricassist.api.errors.logger.error", capture)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/scans/example/images",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 123),
            "scheme": "http",
        }
    )
    request.state.correlation_id = "safe-correlation-id"

    response = await unexpected_error_handler(
        request, RuntimeError("https://secret-presigned-url.invalid")
    )

    assert response.status_code == 500
    assert logged == [
        (
            "Unexpected API error",
            {
                "http_method": "POST",
                "http_path": "/api/v1/scans/example/images",
                "http_status": 500,
                "error_type": "RuntimeError",
            },
        )
    ]


def test_cors_preflight_accepts_analysis_idempotency_header() -> None:
    with TestClient(create_app(Settings(environment="test"), AvailableDatabase())) as client:
        response = client.options(
            "/api/v1/scans/example/analyse",
            headers={
                "Origin": "http://localhost:8081",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,idempotency-key",
            },
        )

    assert response.status_code == 200
    assert "idempotency-key" in response.headers["access-control-allow-headers"].lower()


def test_draft_scan_request_has_no_embedded_images() -> None:
    assert CreateScanRequest().requested_language == "en"
    with pytest.raises(ValidationError):
        CreateScanRequest.model_validate(
            {"requested_language": "en", "images": [{"kind": "garment"}]}
        )


@pytest.mark.parametrize(
    "role",
    [
        "garment_overview",
        "care_label",
        "composition_label",
        "barcode_brand_label",
        "stain_closeup",
        "damage_closeup",
        "construction_detail",
        "other",
    ],
)
def test_image_request_accepts_only_new_typed_roles(role: str) -> None:
    request = ImageRequest.model_validate({"role": role, "content_type": "image/jpeg"})

    assert request.role.value == role


@pytest.mark.parametrize("legacy_role", ["garment", "label", "care-tag"])
def test_image_request_rejects_legacy_roles(legacy_role: str) -> None:
    with pytest.raises(ValidationError):
        ImageRequest.model_validate({"role": legacy_role, "content_type": "image/jpeg"})


class ImageLifecycleSession:
    def __init__(self, responses: list[object | None]) -> None:
        self.responses = responses
        self.added: list[object] = []
        self.committed = False
        self.commit_count = 0

    async def scalar(self, statement: object) -> object | None:
        return self.responses.pop(0)

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.committed = True
        self.commit_count += 1

    async def delete(self, value: object) -> None:
        self.added.append(value)


class PresigningStorage:
    def presign_put(self, *, key: str, content_type: str):
        from fabricassist.application.object_storage import PresignedUpload

        return PresignedUpload(
            "https://storage.invalid/upload",
            {"Content-Type": content_type},
            datetime.now(UTC),
        )


class GarmentThumbnailSession:
    def __init__(self, image: object) -> None:
        self.image = image
        self.scalar_calls = 0

    async def scalars(self, statement: object):
        class Result:
            def all(self) -> list[object]:
                return []

        return Result()

    async def get(self, model: object, identifier: object) -> None:
        return None

    async def scalar(self, statement: object) -> object | None:
        self.scalar_calls += 1
        return self.image


class DownloadStorage:
    def presign_get(self, *, key: str):
        from fabricassist.application.object_storage import PresignedDownload

        return PresignedDownload(
            url=f"https://storage.invalid/private/{key}",
            expires_at=datetime.now(UTC),
        )


class ScanHistorySession:
    def __init__(self, scan: object, image: object) -> None:
        self.scan = scan
        self.image = image

    async def scalars(self, statement: object):
        class Result:
            def __init__(self, scan: object) -> None:
                self.scan = scan

            def all(self) -> list[object]:
                return [self.scan]

        return Result(self.scan)

    async def scalar(self, statement: object) -> object | None:
        return self.image


@pytest.mark.asyncio
async def test_scan_history_lists_owned_results_with_presigned_thumbnails() -> None:
    from fabricassist.api.routes.scans import scan_history
    from fabricassist.infrastructure.persistence.models import Scan, ScanImage, User

    tenant_id = uuid4()
    user = User(
        id=uuid4(), tenant_id=tenant_id, email="customer@example.com", password_hash="x" * 32
    )
    scan = Scan(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=user.id,
        status="completed",
        requested_language="en",
        active_result_id=uuid4(),
        created_at=datetime.now(UTC),
    )
    image = ScanImage(
        id=uuid4(),
        tenant_id=tenant_id,
        scan_id=scan.id,
        role="garment_overview",
        display_order=0,
        object_key="private/tenant/scan/image.jpg",
        upload_token=uuid4(),
        upload_expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )

    response = await scan_history(
        ScanHistorySession(scan, image),  # type: ignore[arg-type]
        user,
        DownloadStorage(),  # type: ignore[arg-type]
    )

    assert response[0].scan_id == scan.id
    assert response[0].result_available
    assert (
        response[0].thumbnail_url == "https://storage.invalid/private/private/tenant/scan/image.jpg"
    )


@pytest.mark.asyncio
async def test_garment_response_exposes_only_presigned_thumbnail_url() -> None:
    from fabricassist.api.routes.garments import response_for
    from fabricassist.infrastructure.persistence.models import Garment, ScanImage

    tenant_id = uuid4()
    garment = Garment(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=uuid4(),
        active_analysis_revision_id=None,
        active_result_id=None,
    )
    image = ScanImage(
        id=uuid4(),
        tenant_id=tenant_id,
        scan_id=uuid4(),
        role="garment_overview",
        display_order=0,
        object_key="private/tenant/garment/image.jpg",
        upload_token=uuid4(),
        upload_expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )

    response = await response_for(
        GarmentThumbnailSession(image),  # type: ignore[arg-type]
        garment,
        DownloadStorage(),  # type: ignore[arg-type]
    )

    assert (
        response.thumbnail_url == "https://storage.invalid/private/private/tenant/garment/image.jpg"
    )
    assert "object_key" not in response.model_dump()


@pytest.mark.asyncio
async def test_duplicate_image_request_reuses_image_without_persisting_a_url() -> None:
    from fabricassist.api.routes.scans import ImageRequest, add_image
    from fabricassist.domain.evidence import ImageRole
    from fabricassist.infrastructure.persistence.models import (
        IdempotencyRecord,
        Scan,
        ScanImage,
        User,
    )

    tenant_id = uuid4()
    user = User(
        id=uuid4(), tenant_id=tenant_id, email="customer@example.com", password_hash="x" * 32
    )
    scan = Scan(
        id=uuid4(), tenant_id=tenant_id, user_id=user.id, status="draft", requested_language="en"
    )
    image = ScanImage(
        id=uuid4(),
        tenant_id=tenant_id,
        scan_id=scan.id,
        role="care_label",
        display_order=0,
        object_key="private/test",
        upload_token=uuid4(),
        upload_expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    record = IdempotencyRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=user.id,
        operation=f"scan-image:{scan.id}",
        idempotency_key="repeat",
        request_fingerprint="",
        response_body={"image_id": str(image.id)},
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    request = ImageRequest(role=ImageRole.CARE_LABEL, content_type="image/jpeg")
    record.request_fingerprint = sha256(
        json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    session = ImageLifecycleSession([scan, record, image])

    response = await add_image(
        scan.id,
        request,
        session,  # type: ignore[arg-type]
        user,
        PresigningStorage(),  # type: ignore[arg-type]
        UploadPolicy(max_images_per_scan=8),
        "repeat",
    )

    assert response.image_id == image.id
    assert response.role.value == "care_label"
    assert session.added == []
    assert not session.committed


@pytest.mark.asyncio
async def test_image_creation_uses_configured_limit_and_persists_one_photo() -> None:
    from fastapi import HTTPException

    from fabricassist.api.routes.scans import add_image
    from fabricassist.domain.evidence import ImageRole
    from fabricassist.infrastructure.persistence.models import Scan, ScanImage, User

    tenant_id = uuid4()
    user = User(
        id=uuid4(), tenant_id=tenant_id, email="customer@example.com", password_hash="x" * 32
    )
    scan = Scan(
        id=uuid4(), tenant_id=tenant_id, user_id=user.id, status="draft", requested_language="en"
    )
    request = ImageRequest(role=ImageRole.STAIN_CLOSEUP, content_type="image/jpeg", display_order=4)
    session = ImageLifecycleSession([scan, 0, 0])

    response = await add_image(
        scan.id,
        request,
        session,  # type: ignore[arg-type]
        user,
        PresigningStorage(),  # type: ignore[arg-type]
        UploadPolicy(max_images_per_scan=1),
        None,
    )

    image = next(value for value in session.added if isinstance(value, ScanImage))
    assert response.image_id == image.id
    assert image.role == "stain_closeup"
    assert image.display_order == 4
    assert session.committed

    full_session = ImageLifecycleSession([scan, 1, 0])
    with pytest.raises(HTTPException, match="Maximum image count"):
        await add_image(
            scan.id,
            request,
            full_session,  # type: ignore[arg-type]
            user,
            PresigningStorage(),  # type: ignore[arg-type]
            UploadPolicy(max_images_per_scan=1),
            None,
        )


@pytest.mark.asyncio
async def test_image_removal_commits_deletion_intent_before_object_io() -> None:
    from fabricassist.api.routes.scans import remove_image
    from fabricassist.infrastructure.persistence.models import Scan, ScanImage, User

    class FailingStorage:
        def delete_object(self, key: str) -> None:
            raise OSError("storage unavailable")

    tenant_id = uuid4()
    user = User(
        id=uuid4(), tenant_id=tenant_id, email="customer@example.com", password_hash="x" * 32
    )
    scan = Scan(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=user.id,
        status="uploading",
        requested_language="en",
    )
    image = ScanImage(
        id=uuid4(),
        tenant_id=tenant_id,
        scan_id=scan.id,
        role="care_label",
        display_order=0,
        object_key="private/test",
        upload_token=uuid4(),
        upload_expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    session = ImageLifecycleSession([scan, image, None])

    await remove_image(
        scan.id,
        image.id,
        session,  # type: ignore[arg-type]
        user,
        FailingStorage(),  # type: ignore[arg-type]
    )

    assert image.deletion_requested_at is not None
    assert session.committed


@pytest.mark.asyncio
async def test_other_tenant_cannot_access_scan() -> None:
    from fastapi import HTTPException

    from fabricassist.api.routes.scans import owned_scan
    from fabricassist.infrastructure.persistence.models import User

    user = User(id=uuid4(), tenant_id=uuid4(), email="customer@example.com", password_hash="x" * 32)
    session = ImageLifecycleSession([None])

    with pytest.raises(HTTPException) as error:
        await owned_scan(session, user, uuid4())  # type: ignore[arg-type]

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_incomplete_upload_cannot_be_analysed() -> None:
    from fastapi import HTTPException
    from starlette.requests import Request

    from fabricassist.api.routes.scans import request_analysis
    from fabricassist.application.jobs import AnalysisJobMessage
    from fabricassist.infrastructure.persistence.models import Scan, User

    class UnusedDispatcher:
        async def dispatch_analysis(
            self,
            message: AnalysisJobMessage,
            *,
            correlation_id: str,
        ) -> None:
            del message, correlation_id

    tenant_id = uuid4()
    user = User(
        id=uuid4(), tenant_id=tenant_id, email="customer@example.com", password_hash="x" * 32
    )
    scan = Scan(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=user.id,
        status="uploading",
        requested_language="en",
    )
    session = ImageLifecycleSession([scan, 0])

    with pytest.raises(HTTPException, match="Complete at least one image") as error:
        await request_analysis(
            scan.id,
            Request({"type": "http"}),
            session,  # type: ignore[arg-type]
            user,
            cast(JobDispatcher, UnusedDispatcher()),
        )

    assert error.value.status_code == 409
    assert not session.committed


@pytest.mark.asyncio
async def test_repeated_qstash_analysis_request_reuses_durable_operation() -> None:
    from starlette.requests import Request

    from fabricassist.api.routes.scans import request_analysis
    from fabricassist.application.jobs import AnalysisJobMessage
    from fabricassist.infrastructure.persistence.models import AnalysisJobOperation, Scan, User

    class RecordingDispatcher:
        def __init__(self) -> None:
            self.messages: list[AnalysisJobMessage] = []

        async def dispatch_analysis(
            self, message: AnalysisJobMessage, *, correlation_id: str
        ) -> None:
            assert correlation_id == "test-correlation"
            self.messages.append(message)

    dispatcher = RecordingDispatcher()

    tenant_id = uuid4()
    user = User(
        id=uuid4(), tenant_id=tenant_id, email="customer@example.com", password_hash="x" * 32
    )
    scan = Scan(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=user.id,
        status="uploading",
        requested_language="en",
    )
    session = ImageLifecycleSession([scan, 1, None])
    request = Request({"type": "http"})
    request.state.correlation_id = "test-correlation"
    first = await request_analysis(
        scan.id,
        request,
        session,  # type: ignore[arg-type]
        user,
        cast(JobDispatcher, dispatcher),
        "repeat-analysis",
    )
    operation = next(value for value in session.added if isinstance(value, AnalysisJobOperation))
    session.responses.extend([scan, 1, operation])
    repeated = await request_analysis(
        scan.id,
        request,
        session,  # type: ignore[arg-type]
        user,
        cast(JobDispatcher, dispatcher),
        "repeat-analysis",
    )

    assert first == repeated
    assert first.operation_key == "repeat-analysis"
    assert len(dispatcher.messages) == 1
    assert session.commit_count == 2


@pytest.mark.asyncio
async def test_completed_image_can_be_removed_with_private_object_cleanup() -> None:
    from fabricassist.api.routes.scans import remove_image
    from fabricassist.infrastructure.persistence.models import Scan, ScanImage, User

    class DeletingStorage:
        def __init__(self) -> None:
            self.keys: list[str] = []

        def delete_object(self, key: str) -> None:
            self.keys.append(key)

    tenant_id = uuid4()
    user = User(
        id=uuid4(), tenant_id=tenant_id, email="customer@example.com", password_hash="x" * 32
    )
    scan = Scan(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=user.id,
        status="uploading",
        requested_language="en",
    )
    image = ScanImage(
        id=uuid4(),
        tenant_id=tenant_id,
        scan_id=scan.id,
        role="care_label",
        display_order=0,
        object_key="private/test/completed",
        upload_token=uuid4(),
        upload_expires_at=datetime.now(UTC) + timedelta(minutes=1),
        completed_at=datetime.now(UTC),
    )
    session = ImageLifecycleSession([scan, image, None])
    storage = DeletingStorage()

    response = await remove_image(
        scan.id,
        image.id,
        session,  # type: ignore[arg-type]
        user,
        storage,  # type: ignore[arg-type]
    )

    assert response.status_code == 204
    assert storage.keys == []
    assert image.deletion_requested_at is not None
    assert any(value.__class__.__name__ == "ObjectDeletionOutbox" for value in session.added)
    assert session.committed
