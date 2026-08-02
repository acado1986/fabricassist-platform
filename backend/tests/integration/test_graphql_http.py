from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.testclient import TestClient

from fabricassist.api.graphql_loaders import GraphQLLoaders
from fabricassist.api.graphql_schema import GraphQLContext, create_graphql_router
from fabricassist.application.garment_analysis_cursor import GarmentAnalysisCursor
from fabricassist.application.garment_history_cursor import GarmentHistoryCursor
from fabricassist.application.storefront_cursors import GarmentCursor, MessageCursor, ScanCursor
from fabricassist.application.storefront_queries import (
    AnalysisRevisionView,
    CareResultView,
    ConversationMessageView,
    GarmentAnalysisHistoryView,
    GarmentDetailView,
    GarmentHistoryView,
    GarmentView,
    ImageMetadataView,
    ResultCompositeView,
    RunView,
    ScanView,
    ServiceEventView,
    StorefrontPrincipal,
    StorefrontQueryPort,
    UsageView,
)
from fabricassist.settings import Settings


class StubStorefrontQueries(StorefrontQueryPort):
    async def list_scans(
        self, principal: StorefrontPrincipal, *, first: int, after: ScanCursor | None
    ) -> tuple[list[ScanView], bool]:
        return [], False

    async def get_scan(self, principal: StorefrontPrincipal, scan_id: UUID) -> ScanView | None:
        return None

    async def get_scans(
        self, principal: StorefrontPrincipal, scan_ids: Sequence[UUID]
    ) -> dict[UUID, ScanView]:
        return {}

    async def list_garments(
        self, principal: StorefrontPrincipal, *, first: int, after: GarmentCursor | None
    ) -> tuple[list[GarmentView], bool]:
        return [
            GarmentView(
                id=UUID("11111111-1111-1111-1111-111111111111"),
                display_name=f"tenant-{principal.tenant_id}",
                archived_at=None,
                active_result_id=None,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        ], False

    async def get_garment(
        self, principal: StorefrontPrincipal, garment_id: UUID
    ) -> GarmentView | None:
        return None

    async def get_garments(
        self, principal: StorefrontPrincipal, garment_ids: Sequence[UUID]
    ) -> dict[UUID, GarmentView]:
        garment_id = UUID("11111111-1111-1111-1111-111111111111")
        if garment_id not in garment_ids:
            return {}
        return {
            garment_id: GarmentView(
                id=garment_id,
                display_name=f"tenant-{principal.tenant_id}",
                archived_at=None,
                active_result_id=None,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        }

    async def list_garment_history(
        self,
        principal: StorefrontPrincipal,
        *,
        first: int,
        after: GarmentHistoryCursor | None,
    ) -> tuple[list[GarmentHistoryView], bool]:
        return [], False

    async def get_garment_detail(
        self,
        principal: StorefrontPrincipal,
        garment_id: UUID,
        *,
        first: int,
        after: GarmentAnalysisCursor | None,
        language: str,
    ) -> GarmentDetailView | None:
        if garment_id != UUID("44444444-4444-4444-4444-444444444444"):
            return None
        return GarmentDetailView(
            id=garment_id,
            display_name="Test garment",
            identifiers=["FA-123"],
            thumbnail_url=None,
            thumbnail_scan_id=None,
            thumbnail_image_id=None,
            last_analysis_at=datetime(2026, 1, 2, tzinfo=UTC),
            analysed_before=True,
            cleaned_before=False,
            active_analysis=None,
            active_result=CareResultView(
                id=UUID("55555555-5555-5555-5555-555555555555"),
                status="released",
                language=language,
                data={"title": "Safe result"},
            ),
            analyses=[
                GarmentAnalysisHistoryView(
                    scan_id=UUID("66666666-6666-6666-6666-666666666666"),
                    status="completed",
                    created_at=datetime(2026, 1, 2, tzinfo=UTC),
                    result_available=True,
                    thumbnail_scan_id=None,
                    thumbnail_image_id=None,
                )
            ],
            analyses_has_more=False,
            service_events=[
                ServiceEventView(
                    id=UUID("77777777-7777-7777-7777-777777777777"),
                    kind="planned",
                    note="Test",
                    created_at=datetime(2026, 1, 2, tzinfo=UTC),
                )
            ],
            observations=[],
        )

    async def list_messages(
        self,
        principal: StorefrontPrincipal,
        *,
        scan_id: UUID,
        first: int,
        after: MessageCursor | None,
    ) -> tuple[list[ConversationMessageView], bool]:
        return [
            ConversationMessageView(
                id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                role="user",
                status="processing",
                text="Any stains?",
                run_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                created_at=datetime(2026, 1, 3, tzinfo=UTC),
            )
        ], False

    async def get_analysis_revision(
        self, principal: StorefrontPrincipal, revision_id: UUID
    ) -> AnalysisRevisionView | None:
        return None

    async def get_analysis_revisions(
        self, principal: StorefrontPrincipal, revision_ids: Sequence[UUID]
    ) -> dict[UUID, AnalysisRevisionView]:
        return {}

    async def get_image_metadata(
        self, principal: StorefrontPrincipal, scan_id: UUID
    ) -> list[ImageMetadataView] | None:
        if scan_id != UUID("88888888-8888-8888-8888-888888888888"):
            return None
        return [
            ImageMetadataView(
                id=UUID("99999999-9999-9999-9999-999999999999"),
                role="care_label",
                display_order=0,
                width=1200,
                height=800,
            )
        ]

    async def get_images_metadata(
        self, principal: StorefrontPrincipal, scan_ids: Sequence[UUID]
    ) -> dict[UUID, list[ImageMetadataView] | None]:
        image_scan_id = UUID("88888888-8888-8888-8888-888888888888")
        return {
            scan_id: (
                [
                    ImageMetadataView(
                        id=UUID("99999999-9999-9999-9999-999999999999"),
                        role="care_label",
                        display_order=0,
                        width=1200,
                        height=800,
                    )
                ]
                if scan_id == image_scan_id
                else None
            )
            for scan_id in scan_ids
        }

    async def get_run(self, principal: StorefrontPrincipal, run_id: UUID) -> RunView | None:
        return None

    async def get_runs(
        self, principal: StorefrontPrincipal, run_ids: Sequence[UUID]
    ) -> dict[UUID, RunView]:
        return {}

    async def get_usage(self, principal: StorefrontPrincipal) -> UsageView | None:
        return None

    async def get_result_composite(
        self, principal: StorefrontPrincipal, scan_id: UUID, *, language: str
    ) -> ResultCompositeView | None:
        return ResultCompositeView(
            scan=ScanView(
                id=scan_id,
                status="processing",
                requested_language=language,
                progress_percent=42,
                analysis_stage="evidence",
                error_code=None,
                garment_id=None,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
            active_analysis=None,
            result=None,
            garment=None,
            identity_candidates=[],
        )


def make_http_app() -> FastAPI:
    app = FastAPI()
    bearer = HTTPBearer()
    queries = StubStorefrontQueries()
    settings = Settings(environment="test")

    async def context(
        credentials: HTTPAuthorizationCredentials = Depends(bearer),  # noqa: B008
    ) -> GraphQLContext:
        assert credentials.credentials == "integration-token"
        principal = StorefrontPrincipal(
            user_id=uuid4(),
            tenant_id=UUID("22222222-2222-2222-2222-222222222222"),
            email="customer@example.test",
            role="customer",
            preferred_language="en",
        )
        return GraphQLContext(
            principal=principal,
            correlation_id="integration-correlation",
            queries=queries,
            loaders=GraphQLLoaders(queries, principal),
        )

    app.include_router(
        create_graphql_router(context_getter=context, settings=settings),
        prefix="/api/v1/graphql",
    )
    return app


def test_authenticated_graphql_http_query_is_query_only_and_tenant_scoped() -> None:
    with TestClient(make_http_app()) as client:
        response = client.post(
            "/api/v1/graphql",
            headers={"Authorization": "Bearer integration-token"},
            json={"query": "{ garments { items { id displayName } } }"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["garments"]["items"][0]["displayName"].startswith("tenant-")
    assert response.json().get("errors") is None


def test_graphql_http_rejects_mutations() -> None:
    with TestClient(make_http_app()) as client:
        response = client.post(
            "/api/v1/graphql",
            headers={"Authorization": "Bearer integration-token"},
            json={"query": "mutation { __typename }"},
        )

    assert response.status_code == 200
    assert response.json()["errors"][0]["message"] == "The GraphQL request could not be completed."


def test_graphql_http_rejects_invalid_opaque_cursor() -> None:
    with TestClient(make_http_app()) as client:
        response = client.post(
            "/api/v1/graphql",
            headers={"Authorization": "Bearer integration-token"},
            json={
                "query": (
                    "query($after: String) { garments(after: $after) { pageInfo { nextCursor } } }"
                ),
                "variables": {"after": "not-a-cursor"},
            },
        )

    assert response.status_code == 200
    assert response.json()["errors"][0]["extensions"]["code"] == "INVALID_PAGINATION"


def test_authenticated_graphql_http_returns_result_composite() -> None:
    scan_id = "33333333-3333-3333-3333-333333333333"
    with TestClient(make_http_app()) as client:
        response = client.post(
            "/api/v1/graphql",
            headers={"Authorization": "Bearer integration-token"},
            json={
                "query": (
                    "query($scanId: UUID!, $language: String!) { "
                    "scanResult(scanId: $scanId, language: $language) { "
                    "scan { id status progressPercent } } }"
                ),
                "variables": {"scanId": scan_id, "language": "en"},
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["scanResult"]["scan"] == {
        "id": scan_id,
        "status": "processing",
        "progressPercent": 42,
    }


def test_authenticated_graphql_http_returns_conversation_run_id() -> None:
    with TestClient(make_http_app()) as client:
        response = client.post(
            "/api/v1/graphql",
            headers={"Authorization": "Bearer integration-token"},
            json={
                "query": (
                    "query($scanId: UUID!) { messages(scanId: $scanId) { "
                    "items { id status runId } } }"
                ),
                "variables": {"scanId": "33333333-3333-3333-3333-333333333333"},
            },
        )

    assert response.status_code == 200
    assert "errors" not in response.json()
    assert response.json()["data"]["messages"]["items"][0]["runId"] == (
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    )


def test_authenticated_graphql_http_returns_garment_detail_without_thumbnail_url() -> None:
    with TestClient(make_http_app()) as client:
        response = client.post(
            "/api/v1/graphql",
            headers={"Authorization": "Bearer integration-token"},
            json={
                "query": (
                    "query($garmentId: UUID!) { garmentDetail(id: $garmentId) { "
                    "id identifiers thumbnailImageId analyses { items { scanId resultAvailable } "
                    "pageInfo { nextCursor } } serviceEvents { kind } activeResult { data } } }"
                ),
                "variables": {"garmentId": "44444444-4444-4444-4444-444444444444"},
            },
        )

    assert response.status_code == 200
    assert "errors" not in response.json()
    detail = response.json()["data"]["garmentDetail"]
    assert detail["identifiers"] == ["FA-123"]
    assert detail["thumbnailImageId"] is None
    assert detail["analyses"]["items"][0]["resultAvailable"] is True


def test_authenticated_graphql_http_returns_image_metadata_without_file_fields() -> None:
    with TestClient(make_http_app()) as client:
        response = client.post(
            "/api/v1/graphql",
            headers={"Authorization": "Bearer integration-token"},
            json={
                "query": (
                    "query($scanId: UUID!) { imageMetadata(scanId: $scanId) { "
                    "id role displayOrder width height } }"
                ),
                "variables": {"scanId": "88888888-8888-8888-8888-888888888888"},
            },
        )

    assert response.status_code == 200
    assert "errors" not in response.json()
    metadata = response.json()["data"]["imageMetadata"][0]
    assert metadata == {
        "id": "99999999-9999-9999-9999-999999999999",
        "role": "care_label",
        "displayOrder": 0,
        "width": 1200,
        "height": 800,
    }
