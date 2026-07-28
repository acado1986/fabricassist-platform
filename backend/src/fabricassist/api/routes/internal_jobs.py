"""Private, signed job-delivery endpoint (excluded from the public schema)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
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
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.jobs.factory import create_job_dispatcher
from fabricassist.infrastructure.jobs.qstash import JobDispatchError
from fabricassist.infrastructure.persistence.models import AnalysisJobOperation
from fabricassist.infrastructure.storage.s3 import S3Storage
from fabricassist.settings import Settings

router = APIRouter(prefix="/internal/jobs", include_in_schema=False)


async def get_session() -> AsyncSession:
    raise RuntimeError("Database session dependency was not configured.")


async def get_settings() -> Settings:
    raise RuntimeError("Settings dependency was not configured.")


async def get_database() -> Database:
    raise RuntimeError("Database dependency was not configured.")


async def get_storage() -> S3Storage:
    raise RuntimeError("Storage dependency was not configured.")


@router.post("/qstash", status_code=204)
async def execute_stage(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[Database, Depends(get_database)],
    storage: Annotated[S3Storage, Depends(get_storage)],
    signature: Annotated[str | None, Header(alias="Upstash-Signature")] = None,
) -> Response:
    raw_body = await request.body()
    try:
        verify_qstash_signature(raw_body=raw_body, signature=signature, settings=settings)
        message = parse_delivery(raw_body)
        result = await execute_checkpoint(
            session=session,
            message=message,
            settings=settings,
            database=database,
            storage=storage,
        )
        if result.continuation is not None:
            await create_job_dispatcher(settings).dispatch_analysis(
                result.continuation,
                correlation_id=str(request.state.correlation_id),
            )
            continuation = await session.scalar(
                select(AnalysisJobOperation).where(
                    AnalysisJobOperation.scan_id == result.continuation.scan_id,
                    AnalysisJobOperation.operation_key == result.continuation.operation_key,
                    AnalysisJobOperation.revision_id == result.continuation.revision_id,
                    AnalysisJobOperation.stage == result.continuation.stage,
                )
            )
            if isinstance(continuation, AnalysisJobOperation):
                continuation.published_at = datetime.now(UTC)
                await session.commit()
    except DeliveryVerificationError:
        return Response(status_code=401)
    except PermanentDeliveryError:
        return Response(status_code=489, headers={"Upstash-NonRetryable-Error": "true"})
    except TemporaryJobError:
        return Response(status_code=503)
    except JobDispatchError:
        return Response(status_code=503)
    return Response(status_code=204)
