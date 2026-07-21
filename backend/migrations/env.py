"""Alembic environment for the FabricAssist PostgreSQL baseline."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from fabricassist.infrastructure.database import normalise_database_url
from fabricassist.infrastructure.persistence.models import Base
from fabricassist.settings import Settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL using the configured FabricAssist database URL."""
    settings = Settings()
    context.configure(
        url=normalise_database_url(settings.database_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations using a synchronous psycopg SQLAlchemy engine."""
    settings = Settings()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = normalise_database_url(settings.database_url)
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
