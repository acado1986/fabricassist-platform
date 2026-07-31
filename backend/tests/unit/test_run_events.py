from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fabricassist.api.routes.runs import sse_frame
from fabricassist.application.ai_runs import ALLOWED_RUN_TRANSITIONS
from fabricassist.infrastructure.persistence.models import AiRunEvent


def test_sse_frame_has_stable_id_event_and_envelope() -> None:
    run_id = uuid4()
    event = AiRunEvent(
        id=uuid4(),
        tenant_id=uuid4(),
        run_id=run_id,
        sequence=4,
        event_type="run.progress",
        data={"stage": "processing", "progress_percent": 50},
        created_at=datetime(2026, 7, 31, tzinfo=UTC),
    )

    frame = sse_frame(event).decode()

    assert frame.startswith("id: 4\nevent: run.progress\ndata: ")
    assert f'"run_id":"{run_id}"' in frame
    assert '"sequence":4' in frame
    assert frame.endswith("\n\n")


def test_run_state_machine_never_reopens_a_terminal_run() -> None:
    assert "running" in ALLOWED_RUN_TRANSITIONS["pending"]
    assert "completed" in ALLOWED_RUN_TRANSITIONS["running"]
    assert not ALLOWED_RUN_TRANSITIONS["completed"]
    assert not ALLOWED_RUN_TRANSITIONS["failed"]
    assert not ALLOWED_RUN_TRANSITIONS["cancelled"]
