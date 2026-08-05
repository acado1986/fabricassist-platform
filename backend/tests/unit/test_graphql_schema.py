from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from inspect import signature
from typing import cast
from uuid import uuid4

import pytest

from fabricassist.api.graphql_loaders import GraphQLLoaders
from fabricassist.api.graphql_schema import (
    GraphQLContext,
    create_schema,
    identity_candidate_type,
)
from fabricassist.application.garment_analysis_cursor import (
    GarmentAnalysisCursor,
    decode_analysis_cursor,
    encode_analysis_cursor,
)
from fabricassist.application.garment_history_cursor import (
    GarmentHistoryCursor,
    decode_history_cursor,
    encode_history_cursor,
)
from fabricassist.application.storefront_cursors import (
    GarmentCursor,
    MessageCursor,
    ScanCursor,
    decode_garment_cursor,
    decode_message_cursor,
    decode_scan_cursor,
    encode_garment_cursor,
    encode_message_cursor,
    encode_scan_cursor,
)
from fabricassist.application.storefront_queries import (
    IdentityCandidateView,
    StorefrontPrincipal,
    StorefrontQueryPort,
)
from fabricassist.settings import Settings


def test_schema_exposes_canonical_queries_only() -> None:
    schema = create_schema(Settings(environment="test"))
    sdl = schema.as_str()

    for field in (
        "currentUser",
        "scans",
        "scan(",
        "garments",
        "garmentHistory",
        "garmentDetail",
        "messages",
        "analysisRevision",
        "scanResult",
        "usage",
    ):
        assert field in sdl
    assert "type Mutation" not in sdl
    assert "mutation" not in sdl.lower()


def test_care_result_uses_a_typed_v2_projection_without_json_fallback() -> None:
    sdl = create_schema(Settings(environment="test")).as_str()

    care_result = sdl[sdl.index("type CareResultType") : sdl.index("type IdentityCandidateType")]
    assert "result: GarmentAnalysisResultType!" in care_result
    assert "data:" not in care_result
    assert "type GarmentAnalysisResultType" in sdl
    assert "prohibitedActions: [CareActionType!]!" in sdl
    assert "stainSteps: [StainStepType!]!" in sdl


def test_identity_candidate_exposes_safe_thumbnail_identifiers() -> None:
    candidate = IdentityCandidateView(
        id=uuid4(),
        garment_id=uuid4(),
        thumbnail_scan_id=uuid4(),
        thumbnail_image_id=uuid4(),
        classification="probable_instance",
        reasons={"source": "exact_image"},
        status="pending",
    )

    view = identity_candidate_type(candidate)

    assert view.thumbnail_scan_id == candidate.thumbnail_scan_id
    assert view.thumbnail_image_id == candidate.thumbnail_image_id

    sdl = create_schema(Settings(environment="test")).as_str()
    assert "thumbnailScanId: UUID" in sdl
    assert "thumbnailImageId: UUID" in sdl


def test_schema_has_query_resource_limits() -> None:
    schema = create_schema(Settings(environment="test", graphql_max_depth=3))

    extension_names = {type(extension).__name__ for extension in schema.extensions}
    assert extension_names >= {"QueryDepthLimiter", "MaxTokensLimiter", "MaxAliasesLimiter"}


def test_production_schema_registers_introspection_blocker_instance() -> None:
    settings = Settings(environment="test")
    settings.environment = "production"
    schema = create_schema(settings)

    extension_names = {type(extension).__name__ for extension in schema.extensions}

    assert "DisableIntrospection" in extension_names


def test_graphql_context_uses_strawberry_fastapi_base_context() -> None:
    from strawberry.fastapi import BaseContext

    assert issubclass(GraphQLContext, BaseContext)


def test_graphql_context_is_transport_safe_and_loaders_are_request_scoped() -> None:
    parameter_names = set(signature(GraphQLContext).parameters)
    assert parameter_names == {"principal", "correlation_id", "queries", "loaders"}
    assert "session" not in parameter_names
    assert "storage" not in parameter_names

    principal = StorefrontPrincipal(
        user_id=uuid4(),
        tenant_id=uuid4(),
        email="customer@example.com",
        role="customer",
        preferred_language="en",
    )
    query_port = cast(StorefrontQueryPort, object())
    first = GraphQLLoaders(query_port, principal)
    second = GraphQLLoaders(query_port, principal)
    assert first.scans is not second.scans
    assert first.garments is not second.garments


def test_garment_history_cursor_round_trips_timestamp_and_null_marker() -> None:
    garment_id = uuid4()
    for timestamp in (None, datetime(2026, 7, 31, 12, tzinfo=UTC)):
        cursor = GarmentHistoryCursor(timestamp, garment_id)
        assert decode_history_cursor(encode_history_cursor(cursor)) == cursor


@pytest.mark.parametrize("value", ["", "not-a-cursor", "eyJhIjpudWxsLCJnIjoiYmFkIn0"])
def test_garment_history_cursor_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid garment history cursor"):
        decode_history_cursor(value)


def test_garment_analysis_cursor_round_trips_timestamp_and_scan_id() -> None:
    cursor = GarmentAnalysisCursor(datetime(2026, 7, 31, 12, tzinfo=UTC), uuid4())
    assert decode_analysis_cursor(encode_analysis_cursor(cursor)) == cursor


@pytest.mark.parametrize("value", ["", "not-a-cursor", "eyJjIjoiYmFkIiwicyI6ImJhZCJ9"])
def test_garment_analysis_cursor_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid garment analysis cursor"):
        decode_analysis_cursor(value)


def test_storefront_cursors_round_trip_with_versioned_opaque_payloads() -> None:
    timestamp = datetime(2026, 7, 31, 12, tzinfo=UTC)
    scan_id = uuid4()
    garment_id = uuid4()
    message_id = uuid4()
    assert decode_scan_cursor(encode_scan_cursor(ScanCursor(timestamp, scan_id))) == ScanCursor(
        timestamp, scan_id
    )
    assert decode_garment_cursor(
        encode_garment_cursor(GarmentCursor(timestamp, garment_id))
    ) == GarmentCursor(timestamp, garment_id)
    assert decode_message_cursor(
        encode_message_cursor(MessageCursor(timestamp, message_id))
    ) == MessageCursor(timestamp, message_id)


@pytest.mark.parametrize(
    "decoder",
    [decode_scan_cursor, decode_garment_cursor, decode_message_cursor],
)
def test_storefront_cursors_reject_unversioned_values(
    decoder: Callable[[str], object],
) -> None:
    with pytest.raises(ValueError, match="Invalid storefront cursor"):
        decoder("eyJjIjoiMjAyNi0wNy0zMVQxMjowMDowMCswMDowMCJ9")
