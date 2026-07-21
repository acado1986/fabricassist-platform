"""Run the development-only Phase 5 seed through the configured database URL."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fabricassist.infrastructure.database import normalise_database_url
from fabricassist.infrastructure.persistence.seeding import seed_development_data
from fabricassist.settings import Settings


def main() -> None:
    """Seed only development data and refuse accidental production use."""
    settings = Settings()
    if settings.environment not in {"development", "test"}:
        raise RuntimeError(
            "Development seed data may only run in development or test environments."
        )

    engine = create_engine(normalise_database_url(settings.database_url), pool_pre_ping=True)
    with Session(engine, expire_on_commit=False) as session:
        tenant, admin = seed_development_data(session)
        session.commit()
        tenant_slug = tenant.slug
        admin_email = admin.email
    engine.dispose()
    print(f"Seeded development tenant {tenant_slug} and non-loginable admin {admin_email}.")


if __name__ == "__main__":
    main()
