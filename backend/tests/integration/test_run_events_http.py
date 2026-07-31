from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from fabricassist.api.routes.runs import run_events
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.persistence.models import AiRun, AiRunEvent


class FakeSession:
    def __init__(self, run: AiRun | None) -> None:
        self.run = run

    async def scalar(self, _statement: object) -> AiRun | None:
        return self.run

    async def rollback(self) -> None:
        return None


class FakeEventSession:
    def __init__(self, events: list[AiRunEvent]) -> None:
        self.events = events

    async def scalars(self, _statement: object) -> FakeEventSession:
        return self

    def all(self) -> list[AiRunEvent]:
        return self.events


class FakeDatabase:
    def __init__(self, events: list[AiRunEvent]) -> None:
        self.events = events

    @asynccontextmanager
    async def session_factory(self) -> AsyncGenerator[FakeEventSession, None]:
        yield FakeEventSession(self.events)


def request() -> Request:
    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/runs/events",
            "headers": [],
            "query_string": b"",
            "client": ("testclient", 123),
            "server": ("testserver", 80),
            "scheme": "http",
        },
        receive,
    )


def make_run(*, tenant_id: UUID, user_id: UUID, run_id: UUID) -> AiRun:
    return AiRun(
        id=run_id,
        tenant_id=tenant_id,
        user_id=user_id,
        scan_id=uuid4(),
        operation="analysis",
        status="running",
        idempotency_key="integration",
        request_fingerprint="f" * 64,
        correlation_id="c" * 36,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_sse_replays_after_cursor_and_closes_on_terminal_event() -> None:
    tenant_id = uuid4()
    user_id = uuid4()
    run_id = uuid4()
    run = make_run(tenant_id=tenant_id, user_id=user_id, run_id=run_id)
    events = [
        AiRunEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            run_id=run_id,
            sequence=2,
            event_type="run.progress",
            data={"stage": "processing"},
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        AiRunEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            run_id=run_id,
            sequence=3,
            event_type="run.completed",
            data={},
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
    ]
    user = SimpleNamespace(id=user_id, tenant_id=tenant_id)

    response = await run_events(
        run_id,
        request(),
        cast(Any, FakeSession(run)),
        cast(Any, user),
        cast(Database, FakeDatabase(events)),
        "1",
    )

    chunks = [chunk async for chunk in response.body_iterator]
    payload = b"".join(cast(list[bytes], chunks)).decode()
    assert response.media_type == "text/event-stream"
    assert "id: 2" in payload
    assert "id: 3" in payload
    assert "event: run.completed" in payload


@pytest.mark.asyncio
async def test_sse_does_not_reveal_cross_tenant_run_existence() -> None:
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    user_id = uuid4()
    run_id = uuid4()
    run = make_run(tenant_id=tenant_id, user_id=user_id, run_id=run_id)
    other_user = SimpleNamespace(id=user_id, tenant_id=other_tenant_id)

    with pytest.raises(HTTPException) as error:
        await run_events(
            run_id,
            request(),
            cast(Any, FakeSession(run if run.tenant_id == other_tenant_id else None)),
            cast(Any, other_user),
            cast(Database, FakeDatabase([])),
            None,
        )

    assert error.value.status_code == 404
