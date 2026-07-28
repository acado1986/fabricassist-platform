"""Private, signed job-delivery endpoint (excluded from the public schema)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from fabricassist.application.qstash import (
    DeliveryVerificationError,
    PermanentDeliveryError,
    TemporaryJobError,
    execute_checkpoint,
    parse_delivery,
    verify_qstash_signature,
)
from fabricassist.settings import Settings

router = APIRouter(prefix="/internal/jobs", include_in_schema=False)


async def get_session() -> AsyncSession:
    raise RuntimeError("Database session dependency was not configured.")


async def get_settings() -> Settings:
    raise RuntimeError("Settings dependency was not configured.")


@router.post("/qstash", status_code=204)
async def execute_stage(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    signature: Annotated[str | None, Header(alias="Upstash-Signature")] = None,
) -> Response:
    raw_body = await request.body()
    try:
        verify_qstash_signature(raw_body=raw_body, signature=signature, settings=settings)
        message = parse_delivery(raw_body)
        await execute_checkpoint(session=session, message=message, settings=settings)
    except DeliveryVerificationError:
        return Response(status_code=401)
    except PermanentDeliveryError:
        return Response(status_code=489, headers={"Upstash-NonRetryable-Error": "true"})
    except TemporaryJobError:
        return Response(status_code=503)
    return Response(status_code=204)
