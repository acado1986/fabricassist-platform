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
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session

from fabricassist.api.main import create_app
from fabricassist.api.routes import scans
from fabricassist.application.analysis import analyse_scan
from fabricassist.infrastructure.database import Database, normalise_database_url
from fabricassist.infrastructure.persistence.models import (
    AnalysisRevision,
    Base,
    CareResult,
    RevisionImage,
    Scan,
    ScanImage,
    Tenant,
    User,
)
from fabricassist.infrastructure.persistence.seeding import (
    DEVELOPMENT_ADMIN_EMAIL,
    seed_development_data,
)
from fabricassist.infrastructure.storage.s3 import S3Storage
from fabricassist.settings import Settings

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
    monkeypatch.setenv("FABRICASSIST_DATABASE_URL", TEST_DATABASE_URL)
    engine = create_engine(normalise_database_url(TEST_DATABASE_URL))
    reset_database(engine)
    config = alembic_config()

    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) >= set(Base.metadata.tables)
    for table_name in Base.metadata.tables:
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if table_name not in {"tenants", "analysis_revision_images"}:
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

    reset_database(engine)
    command.upgrade(config, "20260721_0001")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260723_0010"
    with pytest.raises(RuntimeError, match="breaking garment-intelligence cutover"):
        command.downgrade(config, "20260721_0003")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260723_0010"
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
        session.add_all([scan, image])
        session.commit()
        scan_id = scan.id
        image_id = image.id
        image_key = image.object_key
        tenant_id = tenant.id

    settings = Settings(
        environment="test",
        vision_provider="mock",
        database_url=TEST_DATABASE_URL,
        s3_endpoint_url="http://localhost:9002",
        s3_public_endpoint_url="http://localhost:9002",
        s3_access_key="fabricassist-test",
        s3_secret_key="change-me-local-minio-test",
        s3_bucket="fabricassist-test",
    )
    storage = S3Storage(settings)
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
        analyse_scan(database=database, storage=storage, settings=settings, scan_id=scan_id)
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
    storage = S3Storage(settings)
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
