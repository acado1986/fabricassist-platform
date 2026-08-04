"""Durable aggregate metrics derived from PostgreSQL business state."""
# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.infrastructure.persistence.models import (
    AnalysisBranchResult,
    CanonicalPlanCache,
    ConversationMessage,
    EvidenceCacheEntry,
    GarmentIdentityMatchRun,
    GarmentObservation,
    ModelRun,
    ObjectDeletionOutbox,
    ProductLookupRun,
    RenderedAnswer,
    ReviewCase,
    Scan,
    ValidationReport,
)


def _label(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _sample(name: str, value: object, **labels: object) -> str:
    rendered = ",".join(f'{key}="{_label(item)}"' for key, item in sorted(labels.items()))
    return f"{name}{{{rendered}}} {value}" if rendered else f"{name} {value}"


async def durable_metrics(session: AsyncSession) -> bytes:
    """Render low-cardinality operational aggregates without tenant/user identifiers."""
    lines = [
        "# HELP fabricassist_scans_total Durable scans by lifecycle status.",
        "# TYPE fabricassist_scans_total gauge",
    ]
    for status, count in (
        await session.execute(select(Scan.status, func.count()).group_by(Scan.status))
    ).all():
        lines.append(_sample("fabricassist_scans_total", count, status=status))

    lines.extend(
        [
            "# HELP fabricassist_identity_durable_total Durable identity outcomes.",
            "# TYPE fabricassist_identity_durable_total gauge",
        ]
    )
    for classification, count in (
        await session.execute(
            select(GarmentIdentityMatchRun.classification, func.count()).group_by(
                GarmentIdentityMatchRun.classification
            )
        )
    ).all():
        lines.append(
            _sample(
                "fabricassist_identity_durable_total",
                count,
                classification=classification,
            )
        )

    lines.extend(
        [
            "# HELP fabricassist_product_lookup_durable_total Durable product lookup outcomes.",
            "# TYPE fabricassist_product_lookup_durable_total gauge",
        ]
    )
    for provider, status, count in (
        await session.execute(
            select(ProductLookupRun.provider, ProductLookupRun.status, func.count()).group_by(
                ProductLookupRun.provider, ProductLookupRun.status
            )
        )
    ).all():
        lines.append(
            _sample(
                "fabricassist_product_lookup_durable_total",
                count,
                provider=provider,
                status=status,
            )
        )

    outcome = ValidationReport.payload["outcome"].as_string()
    lines.extend(
        [
            "# HELP fabricassist_validation_durable_total Durable validation outcomes.",
            "# TYPE fabricassist_validation_durable_total gauge",
        ]
    )
    for status, count in (
        await session.execute(select(outcome, func.count()).group_by(outcome))
    ).all():
        lines.append(_sample("fabricassist_validation_durable_total", count, outcome=status))

    for metric_name, model, column in (
        ("fabricassist_conversation_messages", ConversationMessage, ConversationMessage.status),
        ("fabricassist_review_cases", ReviewCase, ReviewCase.status),
        ("fabricassist_deletion_outbox", ObjectDeletionOutbox, ObjectDeletionOutbox.status),
    ):
        lines.extend(
            [
                f"# HELP {metric_name} Durable records by status.",
                f"# TYPE {metric_name} gauge",
            ]
        )
        for status, count in (
            await session.execute(select(column, func.count()).select_from(model).group_by(column))
        ).all():
            lines.append(_sample(metric_name, count, status=status))

    lines.extend(
        [
            "# HELP fabricassist_analysis_branches_durable_total Durable branch state by status.",
            "# TYPE fabricassist_analysis_branches_durable_total gauge",
        ]
    )
    for status, count in (
        await session.execute(
            select(AnalysisBranchResult.status, func.count()).group_by(AnalysisBranchResult.status)
        )
    ).all():
        lines.append(_sample("fabricassist_analysis_branches_durable_total", count, status=status))

    cache_source = AnalysisBranchResult.cache_provenance["source"].as_string()
    lines.extend(
        [
            "# HELP fabricassist_analysis_cache_durable_total Durable v2 branch cache outcomes.",
            "# TYPE fabricassist_analysis_cache_durable_total gauge",
        ]
    )
    for source, count in (
        await session.execute(select(cache_source, func.count()).group_by(cache_source))
    ).all():
        lines.append(_sample("fabricassist_analysis_cache_durable_total", count, source=source))

    observation_count = await session.scalar(select(func.count(GarmentObservation.id)))
    rendered_count = await session.scalar(select(func.count(RenderedAnswer.id)))
    lines.extend(
        [
            "# HELP fabricassist_garment_observations_durable_total "
            "Append-only v2 observation projections.",
            "# TYPE fabricassist_garment_observations_durable_total gauge",
            _sample("fabricassist_garment_observations_durable_total", observation_count),
            "# HELP fabricassist_rendered_answers_durable_total "
            "Persisted deterministic rendered answers.",
            "# TYPE fabricassist_rendered_answers_durable_total gauge",
            _sample("fabricassist_rendered_answers_durable_total", rendered_count),
        ]
    )

    model_count, latency_sum, input_tokens, output_tokens, total_tokens, cost = (
        await session.execute(
            select(
                func.count(ModelRun.id),
                func.coalesce(func.sum(ModelRun.latency_ms), 0),
                func.coalesce(func.sum(ModelRun.input_tokens), 0),
                func.coalesce(func.sum(ModelRun.output_tokens), 0),
                func.coalesce(func.sum(ModelRun.total_tokens), 0),
                func.coalesce(func.sum(ModelRun.estimated_cost_usd), 0),
            )
        )
    ).one()
    lines.extend(
        [
            "# HELP fabricassist_model_runs_durable_total Persisted model/provider runs.",
            "# TYPE fabricassist_model_runs_durable_total gauge",
            _sample("fabricassist_model_runs_durable_total", model_count),
            "# HELP fabricassist_model_latency_milliseconds_total Persisted model latency.",
            "# TYPE fabricassist_model_latency_milliseconds_total counter",
            _sample("fabricassist_model_latency_milliseconds_total", latency_sum),
            "# HELP fabricassist_model_input_tokens_total Persisted input token usage.",
            "# TYPE fabricassist_model_input_tokens_total counter",
            _sample("fabricassist_model_input_tokens_total", input_tokens),
            "# HELP fabricassist_model_output_tokens_total Persisted output token usage.",
            "# TYPE fabricassist_model_output_tokens_total counter",
            _sample("fabricassist_model_output_tokens_total", output_tokens),
            "# HELP fabricassist_model_total_tokens_total Persisted total model token usage.",
            "# TYPE fabricassist_model_total_tokens_total counter",
            _sample("fabricassist_model_total_tokens_total", total_tokens),
            "# HELP fabricassist_model_estimated_cost_usd_total Persisted estimated model cost.",
            "# TYPE fabricassist_model_estimated_cost_usd_total counter",
            _sample(
                "fabricassist_model_estimated_cost_usd_total",
                cost if isinstance(cost, Decimal) else Decimal(cost),
            ),
        ]
    )

    evidence_reuse, canonical_reuse = (
        await session.execute(
            select(
                func.coalesce(
                    select(func.sum(EvidenceCacheEntry.reuse_count)).scalar_subquery(), 0
                ),
                func.coalesce(
                    select(func.sum(CanonicalPlanCache.reuse_count)).scalar_subquery(), 0
                ),
            )
        )
    ).one()
    lines.extend(
        [
            "# HELP fabricassist_cache_reuse_total Durable cache reuse provenance.",
            "# TYPE fabricassist_cache_reuse_total gauge",
            _sample("fabricassist_cache_reuse_total", evidence_reuse, layer="evidence"),
            _sample("fabricassist_cache_reuse_total", canonical_reuse, layer="canonical"),
        ]
    )

    oldest_queued = await session.scalar(
        select(func.min(Scan.created_at)).where(Scan.status == "queued")
    )
    age = (
        max(0.0, (datetime.now(UTC) - oldest_queued).total_seconds())
        if oldest_queued is not None
        else 0.0
    )
    lines.extend(
        [
            "# HELP fabricassist_queue_oldest_age_seconds Age of the oldest queued scan.",
            "# TYPE fabricassist_queue_oldest_age_seconds gauge",
            _sample("fabricassist_queue_oldest_age_seconds", age),
        ]
    )
    return ("\n".join(lines) + "\n").encode()
