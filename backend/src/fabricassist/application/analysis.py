"""Idempotent asynchronous scan orchestration and result rendering."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Literal, cast
from uuid import UUID

from PIL import Image, ImageOps, ImageStat
from sqlalchemy import select

from fabricassist.application.vision import NormalizedImage, VisionProviderError
from fabricassist.domain.care import CARE_RULES_VERSION, DETERGENT_RULES_VERSION, decide_care
from fabricassist.infrastructure.database import Database
from fabricassist.infrastructure.persistence.models import (
    CareResult,
    LabelExtraction,
    ModelRun,
    Scan,
    ScanImage,
)
from fabricassist.infrastructure.storage.s3 import S3Storage
from fabricassist.infrastructure.vision.providers import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    get_vision_provider,
)
from fabricassist.settings import Settings

TEMPLATE_VERSION = "result-v2"


def normalize_image(raw: bytes, *, kind: str = "care_label") -> NormalizedImage:
    """Decode safely, apply orientation, remove metadata, and create a bounded sRGB JPEG."""
    try:
        with Image.open(BytesIO(raw)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            if image.width < 320 or image.height < 320:
                raise ValueError("IMAGE_TOO_SMALL")
            if image.width * image.height > 40_000_000:
                raise ValueError("IMAGE_TOO_LARGE")
            stat = ImageStat.Stat(image.resize((1, 1)))  # pyright: ignore[reportUnknownMemberType]
            brightness = sum(stat.mean) / 3
            if brightness < 20 or brightness > 245:
                raise ValueError("IMAGE_POOR_LIGHTING")
            image.thumbnail((2048, 2048))
            output = BytesIO()
            image.save(output, format="JPEG", quality=90, optimize=True)
    except OSError as error:
        raise ValueError("IMAGE_INVALID") from error
    jpeg = output.getvalue()
    return NormalizedImage(
        jpeg_bytes=jpeg,
        sha256=hashlib.sha256(jpeg).hexdigest(),
        width=image.width,
        height=image.height,
        kind=cast(Literal["garment", "care_label"], kind),
    )


def render_result(canonical: dict[str, object], language: str) -> dict[str, object]:
    """Render the safety-approved canonical object without an additional model call."""
    spanish = language == "es"
    status = str(canonical["status"])
    uncertainties = _render_uncertainties(canonical.get("uncertainties"), spanish)
    if status == "needs_better_image":
        return {
            "title": "Necesitamos una foto más clara" if spanish else "We need a clearer photo",
            "summary": "No podemos confirmar las instrucciones de cuidado todavía."
            if spanish
            else "We cannot confirm care instructions yet.",
            "actions": [],
            "prohibitions": [],
            "professional_only": [],
            "detergent": "",
            "uncertainties": uncertainties,
        }
    if status == "needs_review":
        confirmed_evidence = _render_confirmed_evidence(
            canonical.get("confirmed_evidence"), spanish
        )
        return {
            "title": "Necesitamos verificar algunos detalles"
            if spanish
            else "We need to verify some details",
            "summary": "La etiqueta no aporta evidencia suficiente para dar instrucciones seguras."
            if spanish
            else "The label does not provide enough evidence for safe care instructions.",
            "actions": [],
            "prohibitions": [],
            "professional_only": [],
            "detergent": "",
            "uncertainties": uncertainties,
            "confirmed_evidence": confirmed_evidence,
            "can_continue": bool(confirmed_evidence),
        }
    temperature = canonical.get("wash_temperature_c")
    action_codes = cast(list[str], canonical["actions"])
    prohibition_codes = cast(list[str], canonical["prohibitions"])
    professional_codes = cast(list[str], canonical["professional_only"])
    actions = [
        (
            f"Lavar en agua a un máximo de {temperature} °C."
            if spanish
            else f"Wash in water at a maximum of {temperature} °C."
        )
        if action == "wash_in_water" and temperature
        else action
        for action in action_codes
    ]
    labels = {
        "do_not_wash_in_water": ("No lavar en agua.", "Do not wash in water."),
        "do_not_bleach": ("No usar lejía.", "Do not bleach."),
        "do_not_tumble_dry": ("No usar secadora.", "Do not tumble dry."),
        "do_not_iron": ("No planchar.", "Do not iron."),
        "consult_professional_cleaner": (
            "Consultar a una tintorería profesional.",
            "Consult a professional cleaner.",
        ),
    }
    detergent_labels = {
        "delicates_detergent": ("Detergente para prendas delicadas.", "Delicates detergent."),
        "standard_colour_detergent": (
            "Detergente normal apto para ropa de color.",
            "Standard colour-safe detergent.",
        ),
        "no_domestic_detergent": (
            "No usar detergente doméstico.",
            "Do not use domestic detergent.",
        ),
    }
    detergent_code = str(canonical["detergent"])
    return {
        "title": "Instrucciones de cuidado" if spanish else "Care instructions",
        "summary": "Basadas en la etiqueta detectada."
        if spanish
        else "Based on the detected care label.",
        "actions": actions,
        "prohibitions": [labels[value][0 if spanish else 1] for value in prohibition_codes],
        "professional_only": [labels[value][0 if spanish else 1] for value in professional_codes],
        "detergent": detergent_labels.get(
            detergent_code,
            ("Consultar a un profesional.", "Consult a professional."),
        )[0 if spanish else 1],
        "uncertainties": uncertainties,
        "confirmed_evidence": [],
        "can_continue": False,
    }


def _render_confirmed_evidence(value: object, spanish: bool) -> list[str]:
    """Render label-backed partial facts without presenting a complete care recommendation."""
    raw_values = cast(list[object], value) if isinstance(value, list) else []
    labels = {
        "water_washing_allowed_temperature_unknown": (
            "La etiqueta permite lavar con agua, pero no pudimos confirmar la temperatura.",
            "The label allows water washing, but we could not confirm the temperature.",
        ),
        "bleach_prohibited": ("No usar lejía.", "Do not bleach."),
        "tumble_drying_allowed": ("Se permite usar secadora.", "Tumble drying is allowed."),
        "ironing_allowed": ("Se permite planchar.", "Ironing is allowed."),
        "dry_cleaning_prohibited": ("No limpiar en seco.", "Do not dry clean."),
    }
    return [
        labels[raw][0 if spanish else 1]
        for raw in raw_values
        if isinstance(raw, str) and raw in labels
    ]


def _render_uncertainties(value: object, spanish: bool) -> list[str]:
    """Translate stable internal uncertainty codes before returning a user-facing answer."""
    raw_values = cast(list[object], value) if isinstance(value, list) else []
    labels = {
        "insufficient_label_evidence": (
            "No pudimos verificar suficientes símbolos de la etiqueta.",
            "We could not verify enough care-label symbols.",
        ),
        "wash_instruction_unknown": (
            "No pudimos confirmar si se puede lavar con agua.",
            "We could not confirm whether water washing is allowed.",
        ),
        "wash_process": (
            "No pudimos confirmar el programa de lavado.",
            "We could not confirm the wash cycle.",
        ),
        "tumble_permission": (
            "No pudimos confirmar si se puede usar secadora.",
            "We could not confirm whether tumble drying is allowed.",
        ),
        "iron_permission": (
            "No pudimos confirmar las instrucciones de planchado.",
            "We could not confirm the ironing instructions.",
        ),
        "materials": (
            "No pudimos confirmar la composición del tejido.",
            "We could not confirm the fabric composition.",
        ),
        "original_visible_text": (
            "No pudimos leer todo el texto visible de la etiqueta.",
            "We could not read all visible label text.",
        ),
    }
    fallback = (
        "No pudimos confirmar algunos detalles de cuidado.",
        "We could not confirm some care details.",
    )
    return [
        labels.get(raw, fallback)[0 if spanish else 1] for raw in raw_values if isinstance(raw, str)
    ]


async def analyse_scan(
    *, database: Database, storage: S3Storage, settings: Settings, scan_id: UUID
) -> None:
    """Run one operation safely; all terminal state stays authoritative in PostgreSQL."""
    async with database.session_factory() as session:
        scan = await session.get(Scan, scan_id)
        if scan is None or scan.status in {
            "completed",
            "needs_review",
            "needs_better_image",
            "deleted",
        }:
            return
        now = datetime.now(UTC)
        if (
            scan.analysis_lease_expires_at
            and scan.analysis_lease_expires_at > now
            and scan.status == "processing"
        ):
            return
        scan.status = "processing"
        scan.analysis_stage = "normalizing"
        scan.analysis_lease_expires_at = now + timedelta(minutes=settings.analysis_lease_minutes)
        scan.analysis_attempts += 1
        scan.progress_percent = 20
        await session.commit()
        images = list(
            (
                await session.scalars(
                    select(ScanImage).where(
                        ScanImage.scan_id == scan.id, ScanImage.completed_at.is_not(None)
                    )
                )
            ).all()
        )
        image_kinds = {image.kind for image in images}
        if not image_kinds:
            scan.status, scan.analysis_error_code = "failed", "UPLOAD_MISSING"
            await session.commit()
            return
        try:
            normalized_images = tuple(
                normalize_image(storage.read_object(image.object_key), kind=image.kind)
                for image in sorted(images, key=lambda item: 0 if item.kind == "care_label" else 1)
            )
        except ValueError as error:
            scan.status, scan.analysis_error_code, scan.analysis_stage, scan.progress_percent = (
                "needs_better_image",
                str(error),
                "quality",
                100,
            )
            scan.analysis_lease_expires_at = None
            await session.commit()
            return
        scan.analysis_stage, scan.progress_percent = "extracting", 55
        await session.commit()
        provider = get_vision_provider(settings)
        model_run = ModelRun(
            tenant_id=scan.tenant_id,
            scan_id=scan.id,
            provider=settings.vision_provider,
            model=settings.vision_model or "deterministic-review-safe",
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            request_fingerprint=hashlib.sha256(
                "|".join(f"{image.kind}:{image.sha256}" for image in normalized_images).encode(
                    "ascii"
                )
            ).hexdigest(),
            status="running",
        )
        session.add(model_run)
        await session.flush()
        try:
            provider_result = await provider.extract_label(normalized_images)
        except VisionProviderError as error:
            model_run.status, model_run.error_code = "failed", error.code
            scan.status, scan.analysis_error_code, scan.analysis_stage = (
                "failed",
                f"VISION_{error.code}",
                "failed",
            )
            scan.analysis_lease_expires_at = None
            await session.commit()
            return
        model_run.provider, model_run.model, model_run.latency_ms = (
            provider_result.provider,
            provider_result.model,
            provider_result.latency_ms,
        )
        model_run.input_tokens, model_run.output_tokens, model_run.status = (
            provider_result.input_tokens,
            provider_result.output_tokens,
            "succeeded",
        )
        extraction = LabelExtraction(
            tenant_id=scan.tenant_id,
            scan_id=scan.id,
            model_run_id=model_run.id,
            original_text=provider_result.payload.original_visible_text,
            validated_data=provider_result.payload.model_dump(mode="json"),
            confidence=provider_result.payload.overall_confidence,
            status="validated",
        )
        session.add(extraction)
        canonical = decide_care(provider_result.payload)
        result = CareResult(
            tenant_id=scan.tenant_id,
            scan_id=scan.id,
            extraction_id=extraction.id,
            canonical_data=canonical.model_dump(mode="json"),
            rules_version=CARE_RULES_VERSION,
            detergent_rules_version=DETERGENT_RULES_VERSION,
            status=canonical.status,
        )
        session.add(result)
        scan.status, scan.analysis_stage, scan.progress_percent = canonical.status, "completed", 100
        scan.analysis_lease_expires_at, scan.analysis_error_code = None, None
        await session.commit()
