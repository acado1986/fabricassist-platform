"""Compose PostgreSQL tests for the Phase 5 Alembic baseline."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import Engine, create_engine, insert, inspect, text
from sqlalchemy.orm import Session

from fabricassist.api.main import create_app
from fabricassist.api.routes import scans
from fabricassist.application.garment_analysis import AnalysisReference, GarmentAnalysisRequest
from fabricassist.domain.garment_analysis.models import FabricAssistAnalysisResult
from fabricassist.infrastructure.database import Database, normalise_database_url
from fabricassist.infrastructure.garment_analysis import create_garment_analysis_workflow
from fabricassist.infrastructure.persistence.models import (
    AiRun,
    AiRunImage,
    AnalysisRevision,
    Base,
    CareResult,
    EvidenceDossier,
    ProposedPlan,
    RevisionImage,
    Scan,
    ScanImage,
    Tenant,
    User,
    ValidationReport,
)
from fabricassist.infrastructure.persistence.seeding import (
    DEVELOPMENT_ADMIN_EMAIL,
    seed_development_data,
)
from fabricassist.infrastructure.storage.factory import create_object_storage
from fabricassist.infrastructure.storage.s3 import S3ObjectStorageAdapter
from fabricassist.settings import ModelCapabilityProvider, Settings

TEST_DATABASE_URL = os.environ.get("FABRICASSIST_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="FABRICASSIST_TEST_DATABASE_URL is required for Compose migration tests.",
)


def alembic_config() -> Config:
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[2] / "migrations"))
    return config


def reset_database(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))


def test_empty_and_previous_head_upgrade_with_forward_only_cutover_and_seed_idempotency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert TEST_DATABASE_URL is not None
    monkeypatch.setenv("FABRICASSIST_DATABASE_URL", "postgresql://unreachable.invalid/fabricassist")
    monkeypatch.setenv("FABRICASSIST_DATABASE_MIGRATION_URL", TEST_DATABASE_URL)
    engine = create_engine(normalise_database_url(TEST_DATABASE_URL))
    reset_database(engine)
    config = alembic_config()

    command.upgrade(config, "head")
    inspector = inspect(engine)
    with engine.connect() as connection:
        extensions = set(connection.scalars(text("SELECT extname FROM pg_extension")))
    assert {"citext", "vector"} <= extensions
    assert set(inspector.get_table_names()) >= set(Base.metadata.tables)
    for table_name in Base.metadata.tables:
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if table_name not in {"tenants", "analysis_revision_images", "analysis_job_operations"}:
            assert "tenant_id" in columns

    with Session(engine) as session:
        seed_development_data(session)
        session.commit()
    with Session(engine) as session:
        seed_development_data(session)
        session.commit()
        tenant_count = session.scalar(text("SELECT count(*) FROM tenants"))
        admin_count = session.scalar(
            text("SELECT count(*) FROM users WHERE email = :email"),
            {"email": DEVELOPMENT_ADMIN_EMAIL},
        )
    assert tenant_count == 1
    assert admin_count == 1

    # This is the exact forward-only route from the published production revision.
    # It intentionally never stamps, downgrades, or changes `alembic_version` by hand.
    reset_database(engine)
    command.upgrade(config, "20260731_0022")
    production_origin = inspect(engine)
    garment_columns = {column["name"] for column in production_origin.get_columns("garments")}
    assert {"merged_into_id", "merged_at"} <= garment_columns
    assert "fk_garments_merged_into_id" in {
        foreign_key["name"] for foreign_key in production_origin.get_foreign_keys("garments")
    }
    assert "ix_garments_merged_into_id" in {
        index["name"] for index in production_origin.get_indexes("garments")
    }
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260731_0022"
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260804_0030"

    reset_database(engine)
    command.upgrade(config, "20260729_0018")
    previous = inspect(engine)
    assert "dispatch_correlation_id" not in {
        column["name"] for column in previous.get_columns("conversation_messages")
    }
    command.upgrade(config, "head")
    current = inspect(engine)
    assert {
        "dispatch_correlation_id",
        "dispatch_published_at",
    } <= {column["name"] for column in current.get_columns("conversation_messages")}
    assert {
        "ix_conversation_messages_unpublished",
    } <= {index["name"] for index in current.get_indexes("conversation_messages")}
    assert {
        "ix_analysis_job_operations_unpublished",
    } <= {index["name"] for index in current.get_indexes("analysis_job_operations")}
    assert {"analysis_branch_results", "behavior_versions"} <= set(current.get_table_names())
    assert "evidence_conflicts" in current.get_table_names()
    assert {
        "module_version",
        "workflow_version",
        "merged_schema_version",
        "care_policy_version",
        "confidence_policy_version",
        "retry_policy_version",
        "effective_feature_flags",
        "execution_snapshot",
        "finalized_at",
    } <= {column["name"] for column in current.get_columns("analysis_revisions")}
    assert {
        "analysis_revision_id",
        "analysis_branch_result_id",
        "retry_number",
        "image_count",
        "role_counts",
        "total_tokens",
        "cached_tokens",
        "thought_tokens",
        "tool_tokens",
        "response_model_version",
        "completed_at",
    } <= {column["name"] for column in current.get_columns("model_runs")}
    assert {
        "viewpoint",
        "label_scope",
        "quality_state",
        "blur_score",
        "brightness_score",
        "contrast_score",
        "glare_score",
        "crop_readability_score",
        "orientation_degrees",
        "quality_checked_at",
        "preprocessing_version",
        "normalized_object_key",
    } <= {column["name"] for column in current.get_columns("scan_images")}
    assert {
        "method",
        "water_temperature_c",
        "outcome",
        "occurred_at",
        "detail_schema_version",
        "detail_snapshot",
        "exact_garment_confirmed",
        "invalidated",
    } <= {column["name"] for column in current.get_columns("garment_service_events")}
    assert {
        "field_path",
        "previous_value",
        "corrected_value",
        "source_image_id",
        "source",
        "confirmation",
        "supersedes_correction_id",
    } <= {column["name"] for column in current.get_columns("evidence_corrections")}
    command.downgrade(config, "20260729_0018")
    downgraded = inspect(engine)
    assert "dispatch_correlation_id" not in {
        column["name"] for column in downgraded.get_columns("conversation_messages")
    }
    command.upgrade(config, "head")
    with pytest.raises(RuntimeError, match="breaking garment-intelligence cutover"):
        command.downgrade(config, "20260721_0003")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260804_0030"
    engine.dispose()


def test_cutover_transforms_legacy_result_into_current_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert TEST_DATABASE_URL is not None
    monkeypatch.setenv("FABRICASSIST_DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("FABRICASSIST_DATABASE_MIGRATION_URL", TEST_DATABASE_URL)
    engine = create_engine(normalise_database_url(TEST_DATABASE_URL))
    reset_database(engine)
    config = alembic_config()
    command.upgrade(config, "20260803_0028")
    with Session(engine) as session:
        seed_development_data(session)
        tenant = session.query(Tenant).filter_by(slug="fabricassist-development").one()
        user = session.query(User).filter_by(email=DEVELOPMENT_ADMIN_EMAIL).one()
        scan = Scan(
            id=uuid4(),
            tenant_id=tenant.id,
            user_id=user.id,
            status="completed",
            requested_language="en",
        )
        revision_id = uuid4()
        dossier = EvidenceDossier(
            id=uuid4(), tenant_id=tenant.id, analysis_revision_id=revision_id, payload={}
        )
        plan = ProposedPlan(
            id=uuid4(), tenant_id=tenant.id, analysis_revision_id=revision_id, payload={}
        )
        report = ValidationReport(
            id=uuid4(),
            tenant_id=tenant.id,
            proposed_plan_id=plan.id,
            payload={},
        )
        legacy = CareResult(
            id=uuid4(),
            tenant_id=tenant.id,
            analysis_revision_id=revision_id,
            dossier_id=dossier.id,
            proposed_plan_id=plan.id,
            validation_report_id=report.id,
            status="passed",
            canonical_data={"dossier": {}, "proposal": {}, "validation": {}},
        )
        session.add(scan)
        session.flush()
        # The retained legacy row is inserted using only the 0028 columns;
        # 0029/0030 then perform the forward v2 cutover.
        session.execute(
            insert(AnalysisRevision).values(
                id=revision_id,
                tenant_id=tenant.id,
                scan_id=scan.id,
                revision_number=1,
                status="completed",
            )
        )
        session.add_all([dossier, plan, report])
        session.flush()
        session.add(legacy)
        session.commit()
        legacy_id = legacy.id
    command.upgrade(config, "head")
    with Session(engine) as session:
        transformed = session.get(CareResult, legacy_id)
        assert transformed is not None
        assert transformed.status == "needs_review"
        payload = transformed.canonical_data["garment_analysis_result"]
        assert isinstance(payload, dict)
        current = FabricAssistAnalysisResult.model_validate(payload)
        assert current.care_policy.outcome.value == "needs_review"
        assert "historical_result_unavailable" in current.care_policy.warnings
    engine.dispose()


def test_real_minio_object_and_worker_create_an_active_revision() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(normalise_database_url(TEST_DATABASE_URL))
    with Session(engine) as session:
        seed_development_data(session)
        session.commit()
        tenant = session.query(Tenant).filter_by(slug="fabricassist-development").one()
        user = session.query(User).filter_by(email=DEVELOPMENT_ADMIN_EMAIL).one()
        scan = Scan(
            id=uuid4(),
            tenant_id=tenant.id,
            user_id=user.id,
            status="queued",
            requested_language="en",
        )
        image = ScanImage(
            id=uuid4(),
            tenant_id=tenant.id,
            scan_id=scan.id,
            role="care_label",
            display_order=0,
            object_key=f"integration/{uuid4()}/source.jpg",
            upload_token=uuid4(),
            upload_expires_at=datetime.now(UTC) + timedelta(minutes=1),
            completed_at=datetime.now(UTC),
            mime_type="image/jpeg",
            byte_size=1,
            width=400,
            height=400,
        )
        revision = AnalysisRevision(
            id=uuid4(),
            tenant_id=tenant.id,
            scan_id=scan.id,
            revision_number=1,
            status="queued",
            module_version="garment-analysis-v2",
            workflow_version="asyncio-garment-analysis-v2",
            merged_schema_version="merged-garment-assessment-v2",
            care_policy_version="care-policy-v2",
            confidence_policy_version="confidence-policy-v1",
            retry_policy_version="branch-at-most-two-v1",
            effective_feature_flags={"stain_analysis": False},
        )
        run = AiRun(
            id=uuid4(),
            tenant_id=tenant.id,
            user_id=user.id,
            scan_id=scan.id,
            operation="scan_analysis",
            status="running",
            idempotency_key=f"integration:{scan.id}",
            request_fingerprint="0" * 64,
            correlation_id=str(uuid4()),
        )
        # These models intentionally have no SQLAlchemy relationships. Flush
        # principal rows before adding FK-only v2 workflow records.
        session.add_all([scan, image])
        session.flush()
        session.add_all(
            [
                revision,
                run,
                RevisionImage(tenant_id=tenant.id, revision_id=revision.id, image_id=image.id),
                AiRunImage(tenant_id=tenant.id, run_id=run.id, image_id=image.id),
            ]
        )
        session.commit()
        scan_id = scan.id
        image_id = image.id
        image_key = image.object_key
        tenant_id = tenant.id
        revision_id = revision.id
        run_id = run.id

    settings = Settings(
        environment="test",
        garment_analysis_provider=ModelCapabilityProvider.MOCK,
        database_url=TEST_DATABASE_URL,
        s3_endpoint_url="http://localhost:9002",
        s3_public_endpoint_url="http://localhost:9002",
        s3_access_key="fabricassist-test",
        s3_secret_key="change-me-local-minio-test",
        s3_bucket="fabricassist-test",
    )
    storage = create_object_storage(settings)
    assert isinstance(storage, S3ObjectStorageAdapter)
    raw = BytesIO()
    Image.new("RGB", (400, 400), "white").save(raw, "JPEG")
    storage._client.put_object(  # pyright: ignore[reportPrivateUsage]
        Bucket=settings.s3_bucket,
        Key=image_key,
        Body=raw.getvalue(),
        ContentType="image/jpeg",
    )
    assert storage.verify_image(image_key, "image/jpeg").width == 400

    database = Database(TEST_DATABASE_URL)
    asyncio.run(
        create_garment_analysis_workflow(
            database=database, storage=storage, settings=settings
        ).execute(
            GarmentAnalysisRequest(
                reference=AnalysisReference(
                    tenant_id=tenant_id,
                    scan_id=scan_id,
                    run_id=run_id,
                    revision_id=revision_id,
                ),
                correlation_id=str(uuid4()),
            )
        )
    )
    asyncio.run(database.close())

    with Session(engine) as session:
        persisted = session.get(Scan, scan_id)
        revision = session.query(AnalysisRevision).filter_by(scan_id=scan_id).one()
        membership = session.query(RevisionImage).filter_by(revision_id=revision.id).one()
        result = session.query(CareResult).filter_by(analysis_revision_id=revision.id).one()
        assert persisted is not None
        assert persisted.active_analysis_revision_id == revision.id
        assert persisted.active_result_id == result.id
        assert membership.image_id == image_id
        assert membership.tenant_id == tenant_id
    storage.delete_object(image_key)
    engine.dispose()


def test_real_api_upload_completion_enforces_user_and_tenant_ownership() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(normalise_database_url(TEST_DATABASE_URL))
    with Session(engine) as session:
        seed_development_data(session)
        session.commit()
        owner = session.query(User).filter_by(email=DEVELOPMENT_ADMIN_EMAIL).one()
        owner_id = owner.id
        owner_tenant_id = owner.tenant_id
        other_tenant = Tenant(id=uuid4(), slug=f"other-{uuid4().hex[:8]}", name="Other")
        other_user = User(
            id=uuid4(),
            tenant_id=other_tenant.id,
            email="other@example.com",
            password_hash="x" * 32,
        )
        session.add_all([other_tenant, other_user])
        session.commit()
        other_user_id = other_user.id
        other_tenant_id = other_tenant.id

    owner = User(
        id=owner_id,
        tenant_id=owner_tenant_id,
        email=DEVELOPMENT_ADMIN_EMAIL,
        password_hash="x" * 32,
    )
    other_user = User(
        id=other_user_id,
        tenant_id=other_tenant_id,
        email="other@example.com",
        password_hash="x" * 32,
    )

    settings = Settings(
        environment="test",
        database_url=TEST_DATABASE_URL,
        s3_endpoint_url="http://localhost:9002",
        s3_public_endpoint_url="http://localhost:9002",
        s3_access_key="fabricassist-test",
        s3_secret_key="change-me-local-minio-test",
        s3_bucket="fabricassist-test",
    )
    storage = create_object_storage(settings)
    assert isinstance(storage, S3ObjectStorageAdapter)
    database = Database(TEST_DATABASE_URL)
    app = create_app(settings, database)

    async def current_owner() -> User:
        return owner

    app.dependency_overrides[scans.get_current_user] = current_owner
    app.dependency_overrides[scans.get_storage] = lambda: storage
    with TestClient(app) as client:
        scan_response = client.post("/api/v1/scans", json={"requested_language": "en"})
        assert scan_response.status_code == 201
        scan_id = scan_response.json()["scan_id"]
        instruction = client.post(
            f"/api/v1/scans/{scan_id}/images",
            json={"role": "care_label", "content_type": "image/jpeg", "display_order": 0},
        )
        assert instruction.status_code == 201
        image_id = instruction.json()["image_id"]
        with Session(engine) as session:
            image = session.get(ScanImage, image_id)
            assert image is not None
            image_key = image.object_key
        raw = BytesIO()
        Image.new("RGB", (400, 400), "white").save(raw, "JPEG")
        storage._client.put_object(  # pyright: ignore[reportPrivateUsage]
            Bucket=settings.s3_bucket,
            Key=image_key,
            Body=raw.getvalue(),
            ContentType="image/jpeg",
        )
        completed = client.post(
            f"/api/v1/scans/{scan_id}/uploads/complete",
            json={"image_id": image_id, "content_type": "image/jpeg"},
        )
        assert completed.status_code == 200
        assert completed.json()["images_completed"] == 1

        async def current_other_user() -> User:
            return other_user

        app.dependency_overrides[scans.get_current_user] = current_other_user
        denied = client.get(f"/api/v1/scans/{scan_id}")
        assert denied.status_code == 404
    storage.delete_object(image_key)
    engine.dispose()
