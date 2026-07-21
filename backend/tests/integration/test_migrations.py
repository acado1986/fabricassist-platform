"""Compose PostgreSQL tests for the Phase 5 Alembic baseline."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session

from fabricassist.infrastructure.database import normalise_database_url
from fabricassist.infrastructure.persistence.models import Base
from fabricassist.infrastructure.persistence.seeding import (
    DEVELOPMENT_ADMIN_EMAIL,
    seed_development_data,
)

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


def test_empty_upgrade_downgrade_round_trip_and_seed_idempotency(
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
        if table_name != "tenants":
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

    command.downgrade(config, "base")
    assert not set(inspect(engine).get_table_names()).intersection(Base.metadata.tables)
    command.upgrade(config, "20260721_0001")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260721_0002"
    engine.dispose()
