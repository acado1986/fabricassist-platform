"""Server-owned contextual message orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.conversation_provider import ConversationProvider
from fabricassist.application.policies import ConversationPolicy
from fabricassist.domain.care import validate_care_plan
from fabricassist.domain.conversations import ConversationContext
from fabricassist.domain.evidence import GarmentEvidenceDossier
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.persistence.models import (
    CareResult,
    ConversationMessage,
    ConversationSummary,
    EvidenceDossier,
    GarmentServiceEvent,
    ModelRun,
    RevisionImage,
    ScanImage,
)


def select_relevant_image_ids(images: Sequence[ScanImage], user_text: str) -> list[UUID]:
    """Select a bounded, role-led image subset without trusting user text as instructions."""
    lowered = user_text.casefold()
    preferred_roles = ["care_label", "composition_label"]
    if any(term in lowered for term in ("stain", "spot", "mancha", "tache")):
        preferred_roles.insert(0, "stain_closeup")
    if any(term in lowered for term in ("damage", "tear", "hole", "daño", "rotura")):
        preferred_roles.insert(0, "damage_closeup")
    selected = [image.id for role in preferred_roles for image in images if image.role == role]
    selected.extend(image.id for image in images if image.id not in selected)
    return selected[:8]


async def build_context(
    session: AsyncSession,
    message: ConversationMessage,
    policy: ConversationPolicy,
) -> ConversationContext:
    result = await session.get(CareResult, message.care_result_id)
    dossier = (
        await session.scalar(select(EvidenceDossier).where(EvidenceDossier.id == result.dossier_id))
        if result
        else None
    )
    summary = await session.scalar(
        select(ConversationSummary)
        .where(ConversationSummary.thread_id == message.thread_id)
        .order_by(ConversationSummary.version.desc())
    )
    history = list(
        (
            await session.scalars(
                select(GarmentServiceEvent)
                .where(GarmentServiceEvent.garment_id == message.garment_id)
                .order_by(GarmentServiceEvent.created_at.desc())
                .limit(20)
            )
        ).all()
    )
    recent = list(
        (
            await session.scalars(
                select(ConversationMessage)
                .where(
                    ConversationMessage.thread_id == message.thread_id,
                    ConversationMessage.id != message.id,
                )
                .order_by(ConversationMessage.created_at.desc())
                .limit(policy.recent_message_limit)
            )
        ).all()
    )
    images = list(
        (
            await session.scalars(
                select(ScanImage)
                .join(RevisionImage, RevisionImage.image_id == ScanImage.id)
                .where(RevisionImage.revision_id == message.analysis_revision_id)
                .order_by(ScanImage.display_order, ScanImage.created_at)
            )
        ).all()
    )
    if result is None or dossier is None:
        raise ValueError("CONVERSATION_CONTEXT_UNAVAILABLE")
    return ConversationContext(
        garment_id=message.garment_id,
        analysis_revision_id=message.analysis_revision_id,
        dossier=dossier.payload,
        validated_plan=result.canonical_data.get("proposal", {}),
        validation=result.canonical_data.get("validation", {}),
        service_history=[{"kind": item.kind, "note": item.note} for item in history],
        summary=summary.payload if summary else None,
        recent_messages=[{"role": item.role, "text": item.text} for item in reversed(recent)],
        relevant_image_ids=select_relevant_image_ids(images, message.text)[
            : policy.relevant_image_limit
        ],
    )


async def answer_message(
    session: AsyncSession,
    message_id: object,
    conversation_provider: ConversationProvider,
    policy: ConversationPolicy,
) -> None:
    message = await session.scalar(
        select(ConversationMessage).where(ConversationMessage.id == message_id).with_for_update()
    )
    if message is None or message.role != "user" or message.status == "completed":
        return
    message.status = "processing"
    context = await build_context(session, message, policy)
    model_run = ModelRun(
        id=uuid4(),
        tenant_id=message.tenant_id,
        scan_id=message.scan_id,
        operation="conversation",
        provider=conversation_provider.descriptor.provider,
        model=conversation_provider.descriptor.model,
        prompt_version="conversation-v1",
        schema_version="conversation-v1",
        request_fingerprint=sha256(
            f"{message.analysis_revision_id}:{message.id}".encode()
        ).hexdigest(),
        status="processing",
    )
    session.add(model_run)
    await session.flush()
    result = await conversation_provider.answer(context, message.text)
    proposal = result.proposal
    model_run.provider = result.provider
    model_run.model = result.model
    model_run.latency_ms = result.latency_ms
    model_run.input_tokens = result.input_tokens
    model_run.output_tokens = result.output_tokens
    model_run.estimated_cost_usd = Decimal(0) if result.provider == "mock" else None
    model_run.status = "completed"
    dossier = GarmentEvidenceDossier.model_validate(context.dossier)
    reports = [validate_care_plan(dossier, claim.plan) for claim in proposal.actionable_claims]
    blocked = any(
        report.outcome.value in {"blocked", "needs_review", "needs_better_image"}
        for report in reports
    )
    assistant = ConversationMessage(
        id=uuid4(),
        tenant_id=message.tenant_id,
        thread_id=message.thread_id,
        scan_id=message.scan_id,
        garment_id=message.garment_id,
        role="assistant",
        status="blocked" if blocked else "completed",
        text=proposal.text,
        analysis_revision_id=message.analysis_revision_id,
        care_result_id=message.care_result_id,
        model_run_id=model_run.id,
        actionable_claims={
            "claims": [claim.model_dump(mode="json") for claim in proposal.actionable_claims]
        },
        evidence_ids={"ids": [str(x) for x in proposal.evidence_ids]},
        uncertainties={"items": proposal.uncertainties},
        follow_up_questions={"items": proposal.follow_up_questions},
        validation_report={"reports": [report.model_dump(mode="json") for report in reports]},
        completed_at=datetime.now(UTC),
    )
    session.add(assistant)
    message.status = "completed"
    message.completed_at = datetime.now(UTC)
    message_count = await session.scalar(
        select(func.count())
        .select_from(ConversationMessage)
        .where(ConversationMessage.thread_id == message.thread_id)
    )
    if message_count and message_count % 8 == 0:
        prior_version = await session.scalar(
            select(func.coalesce(func.max(ConversationSummary.version), 0)).where(
                ConversationSummary.thread_id == message.thread_id
            )
        )
        session.add(
            ConversationSummary(
                id=uuid4(),
                tenant_id=message.tenant_id,
                thread_id=message.thread_id,
                version=int(prior_version or 0) + 1,
                through_message_id=assistant.id,
                payload={
                    "schema_version": "conversation-summary-v1",
                    "last_user_message": message.text[:500],
                    "last_assistant_message": proposal.text[:500],
                },
            )
        )
    await session.commit()


async def answer_message_by_id(
    database: Database,
    message_id: object,
    conversation_provider: ConversationProvider,
    policy: ConversationPolicy,
) -> None:
    async with database.session_factory() as session:
        await answer_message(
            session,
            message_id,
            conversation_provider,
            policy,
        )
