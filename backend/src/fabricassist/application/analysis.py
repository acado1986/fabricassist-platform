"""Revision-aware evidence → proposal → validator orchestration."""
# pyright: reportUnknownParameterType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportOptionalOperand=false

from __future__ import annotations

import hashlib
from io import BytesIO
from uuid import UUID, uuid4

from PIL import Image, ImageOps
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.planning import MockCarePlanningProvider
from fabricassist.application.products import (
    PersistedProductLookup,
    get_product_provider,
    lookup_and_record,
    product_lookup_from_run,
)
from fabricassist.application.vision import (
    NormalizedImage,
    VisionEvidenceProvider,
    decode_barcodes,
)
from fabricassist.domain.care import (
    CareValidationReport,
    ProposedCarePlan,
    ValidationOutcome,
    validate_care_plan,
)
from fabricassist.domain.evidence import GarmentEvidenceDossier, ImageRole, merge_evidence
from fabricassist.domain.identity import IdentityClassification
from fabricassist.domain.products import ProductLookupError, normalize_barcode
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.persistence.models import (
    AnalysisRevision,
    CareResult,
    EvidenceDossier,
    Garment,
    GarmentIdentifier,
    GarmentIdentityMatchRun,
    GarmentObservation,
    ProductLookupRun,
    ProposedPlan,
    RenderedAnswer,
    RevisionImage,
    Scan,
    ScanImage,
    ValidationReport,
)
from fabricassist.infrastructure.storage.s3 import S3Storage
from fabricassist.infrastructure.vision.providers import get_vision_provider
from fabricassist.settings import Settings

TEMPLATE_VERSION = "rich-result-v1"


def normalize_image(raw: bytes, image_id: UUID, role: str) -> NormalizedImage:
    try:
        with Image.open(BytesIO(raw)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            if image.width < 320 or image.height < 320:
                raise ValueError("IMAGE_TOO_SMALL")
            image.thumbnail((2048, 2048))
            data = BytesIO()
            image.save(data, "JPEG", quality=90)
    except OSError as error:
        raise ValueError("IMAGE_INVALID") from error
    jpeg = data.getvalue()
    return NormalizedImage(
        image_id=image_id,
        jpeg_bytes=jpeg,
        sha256=hashlib.sha256(jpeg).hexdigest(),
        width=image.width,
        height=image.height,
        role=ImageRole(role),
    )


def render_rich_result(
    dossier: GarmentEvidenceDossier,
    proposal: ProposedCarePlan,
    report: CareValidationReport,
    language: str,
    product_lookup: PersistedProductLookup | None = None,
) -> dict[str, object]:
    es = language == "es"
    blocked = report.outcome in {
        ValidationOutcome.BLOCKED,
        ValidationOutcome.NEEDS_REVIEW,
        ValidationOutcome.NEEDS_BETTER_IMAGE,
    }
    return {
        "template_version": TEMPLATE_VERSION,
        "title": "Guía de cuidado validada" if es else "Validated care guidance",
        "validation_state": report.outcome.value,
        "warnings": report.warnings,
        "violations": report.violations,
        "sources": [
            {
                "kind": "photographed",
                "image_id": str(f.source.image_id),
                "fact": f.code,
                "permission": f.permission,
                "temperature_c": f.temperature_c,
            }
            for f in dossier.care_facts
        ],
        "preparation": proposal.preparation,
        "stain_guidance": proposal.stain_guidance,
        "cleaning": proposal.cleaning.model_dump(),
        "detergent": proposal.detergent,
        "drying": proposal.drying,
        "ironing": proposal.ironing,
        "professional_care": proposal.professional_care,
        "prohibitions": proposal.prohibited_actions,
        "uncertainties": proposal.uncertainties,
        "follow_up_questions": proposal.follow_up_questions,
        "actionable": not blocked,
        "change_summary": "Initial revision" if es else "Initial revision",
        "product_information": (
            {
                "barcode": product_lookup.barcode,
                "status": product_lookup.status,
                "provider": product_lookup.provider,
                "source_name": product_lookup.source_name,
                "source_reference": product_lookup.source_reference,
                "license_name": product_lookup.license_name,
                "retrieved_at": (
                    product_lookup.retrieved_at.isoformat()
                    if product_lookup.retrieved_at is not None
                    else None
                ),
                "product": product_lookup.product,
            }
            if product_lookup is not None
            else None
        ),
    }


async def _lookup_barcodes_from_images(
    *,
    session: AsyncSession,
    scan: Scan,
    provider: VisionEvidenceProvider,
    normalized: tuple[NormalizedImage, ...],
    settings: Settings,
) -> PersistedProductLookup | None:
    """Use OCR/vision only to locate barcode digits, then validate locally."""
    barcode_images = tuple(
        image for image in normalized if image.role is ImageRole.BARCODE_BRAND_LABEL
    )
    if barcode_images:
        candidates = (
            *decode_barcodes(barcode_images),
            *await provider.extract_barcode_candidates(barcode_images),
        )
        for candidate in candidates:
            try:
                barcode = normalize_barcode(candidate.value)
            except ValueError:
                continue
            existing = await session.scalar(
                select(ProductLookupRun).where(
                    ProductLookupRun.scan_id == scan.id,
                    ProductLookupRun.tenant_id == scan.tenant_id,
                    ProductLookupRun.barcode == barcode,
                )
            )
            if existing is not None:
                return product_lookup_from_run(existing)
            try:
                return await lookup_and_record(
                    session=session,
                    scan=scan,
                    barcode=barcode,
                    provider=get_product_provider(settings),
                    cache_minutes=settings.product_cache_minutes,
                )
            except ProductLookupError:
                # Product enrichment is optional: catalog outages cannot make a
                # photographed-label analysis fail or weaken its safety gate.
                return None
    run = await session.scalar(
        select(ProductLookupRun)
        .where(ProductLookupRun.scan_id == scan.id, ProductLookupRun.tenant_id == scan.tenant_id)
        .order_by(ProductLookupRun.created_at.desc())
    )
    return product_lookup_from_run(run) if isinstance(run, ProductLookupRun) else None


async def analyse_scan(
    *, database: Database, storage: S3Storage, settings: Settings, scan_id: UUID
) -> None:
    async with database.session_factory() as session:
        scan = await session.get(Scan, scan_id)
        if scan is None or scan.status in {"completed", "deleted"}:
            return
        images = list(
            (
                await session.scalars(
                    select(ScanImage)
                    .where(ScanImage.scan_id == scan.id, ScanImage.completed_at.is_not(None))
                    .order_by(ScanImage.display_order)
                )
            ).all()
        )
        if not images:
            scan.status = "failed"
            scan.analysis_error_code = "UPLOAD_MISSING"
            await session.commit()
            return
        scan.status = "processing"
        scan.analysis_stage = "evidence"
        scan.progress_percent = 25
        try:
            normalized = tuple(
                normalize_image(storage.read_object(i.object_key), i.id, i.role) for i in images
            )
        except ValueError as error:
            scan.status = "needs_better_image"
            scan.analysis_error_code = str(error)
            scan.progress_percent = 100
            await session.commit()
            return
        number = (
            await session.scalar(
                select(func.coalesce(func.max(AnalysisRevision.revision_number), 0)).where(
                    AnalysisRevision.scan_id == scan.id
                )
            )
        ) + 1
        garment = None
        identity_classification = IdentityClassification.NEW_GARMENT
        linked_before_analysis = scan.garment_id is not None
        if scan.garment_id is not None:
            garment = await session.get(Garment, scan.garment_id)
            if garment is not None:
                identity_classification = IdentityClassification.EXACT_INSTANCE
        if garment is None:
            garment = Garment(id=uuid4(), tenant_id=scan.tenant_id, user_id=scan.user_id)
            session.add(garment)
            await session.flush()
            session.add(
                GarmentIdentifier(
                    id=uuid4(),
                    tenant_id=scan.tenant_id,
                    garment_id=garment.id,
                    identifier_type="fabricassist_serial",
                    normalized_value=f"FA-{garment.id.hex.upper()}",
                )
            )
            scan.garment_id = garment.id
        session.add(
            GarmentIdentityMatchRun(
                id=uuid4(),
                tenant_id=scan.tenant_id,
                scan_id=scan.id,
                classification=identity_classification.value,
                reasons={
                    "source": "confirmed_scan_link" if linked_before_analysis else "new_analysis"
                },
            )
        )
        revision = AnalysisRevision(
            id=uuid4(),
            tenant_id=scan.tenant_id,
            scan_id=scan.id,
            garment_id=garment.id,
            revision_number=number,
            status="processing",
        )
        session.add(revision)
        await session.flush()
        for image in images:
            session.add(
                RevisionImage(
                    tenant_id=scan.tenant_id,
                    revision_id=revision.id,
                    image_id=image.id,
                )
            )
        provider = get_vision_provider(settings)
        extracted = await provider.extract_evidence(normalized)
        product_lookup = await _lookup_barcodes_from_images(
            session=session, scan=scan, provider=provider, normalized=normalized, settings=settings
        )
        prior = None
        if garment.active_analysis_revision_id is not None:
            previous = await session.scalar(
                select(EvidenceDossier).where(
                    EvidenceDossier.analysis_revision_id == garment.active_analysis_revision_id
                )
            )
            if previous is not None:
                prior = GarmentEvidenceDossier.model_validate(previous.payload)
        dossier = merge_evidence(prior, extracted.delta)
        evidence = EvidenceDossier(
            id=uuid4(),
            tenant_id=scan.tenant_id,
            analysis_revision_id=revision.id,
            payload=dossier.model_dump(mode="json"),
        )
        session.add(evidence)
        for observation in extracted.delta.observations:
            session.add(
                GarmentObservation(
                    id=uuid4(),
                    tenant_id=scan.tenant_id,
                    garment_id=garment.id,
                    analysis_revision_id=revision.id,
                    observation_type=observation.kind,
                    stability="condition" if observation.time_varying else "stable",
                    value={
                        "value": observation.value,
                        "source_image_id": str(observation.source.image_id),
                    },
                    confidence=float(observation.confidence),
                )
            )
        planner = MockCarePlanningProvider()
        proposal = await planner.propose_plan(dossier)
        report = validate_care_plan(dossier, proposal)
        retried = False
        if report.repairable and report.outcome == ValidationOutcome.BLOCKED:
            retried = True
            proposal = await planner.propose_plan(dossier, tuple(report.violations))
            report = validate_care_plan(dossier, proposal)
        plan = ProposedPlan(
            id=uuid4(),
            tenant_id=scan.tenant_id,
            analysis_revision_id=revision.id,
            retry_number=1 if retried else 0,
            payload=proposal.model_dump(mode="json"),
        )
        session.add(plan)
        await session.flush()
        validation = ValidationReport(
            id=uuid4(),
            tenant_id=scan.tenant_id,
            proposed_plan_id=plan.id,
            payload=report.model_dump(mode="json"),
        )
        session.add(validation)
        await session.flush()
        result = CareResult(
            id=uuid4(),
            tenant_id=scan.tenant_id,
            analysis_revision_id=revision.id,
            dossier_id=evidence.id,
            proposed_plan_id=plan.id,
            validation_report_id=validation.id,
            status=report.outcome.value,
            canonical_data={
                "dossier": dossier.model_dump(mode="json"),
                "proposal": proposal.model_dump(mode="json"),
                "validation": report.model_dump(mode="json"),
            },
        )
        session.add(result)
        await session.flush()
        for lang in ("en", "es"):
            session.add(
                RenderedAnswer(
                    id=uuid4(),
                    tenant_id=scan.tenant_id,
                    care_result_id=result.id,
                    language=lang,
                    template_version=TEMPLATE_VERSION,
                    answer=render_rich_result(dossier, proposal, report, lang, product_lookup),
                )
            )
        revision.status = "completed"
        scan.active_analysis_revision_id = revision.id
        garment.active_analysis_revision_id = revision.id
        garment.active_result_id = result.id
        scan.active_result_id = result.id
        scan.status = (
            "completed"
            if report.outcome in {ValidationOutcome.PASSED, ValidationOutcome.PASSED_WITH_WARNINGS}
            else (
                "needs_review"
                if report.outcome == ValidationOutcome.NEEDS_REVIEW
                else "needs_better_image"
                if report.outcome == ValidationOutcome.NEEDS_BETTER_IMAGE
                else "needs_review"
            )
        )
        scan.analysis_stage = "completed"
        scan.progress_percent = 100
        await session.commit()
