"""Development-only baseline seed helpers with no authentication behavior."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fabricassist.infrastructure.persistence.models import Tenant, User

DEVELOPMENT_TENANT_SLUG = "fabricassist-development"
DEVELOPMENT_ADMIN_EMAIL = "admin@fabricassist.local"
# This marker is intentionally not a password hash and cannot be used to authenticate.
PHASE_6_AUTH_PLACEHOLDER = "phase-6-authentication-not-implemented"


def seed_development_data(session: Session) -> tuple[Tenant, User]:
    """Create the fixed development records once, without committing the caller's transaction."""
    tenant = session.scalar(select(Tenant).where(Tenant.slug == DEVELOPMENT_TENANT_SLUG))
    if tenant is None:
        tenant = Tenant(slug=DEVELOPMENT_TENANT_SLUG, name="FabricAssist Development")
        session.add(tenant)
        session.flush()

    admin = session.scalar(
        select(User).where(User.tenant_id == tenant.id, User.email == DEVELOPMENT_ADMIN_EMAIL)
    )
    if admin is None:
        admin = User(
            tenant_id=tenant.id,
            email=DEVELOPMENT_ADMIN_EMAIL,
            password_hash=PHASE_6_AUTH_PLACEHOLDER,
            role="admin",
            preferred_language="en",
        )
        session.add(admin)
        session.flush()
    return tenant, admin
