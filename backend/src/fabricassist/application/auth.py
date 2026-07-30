"""Session use cases; raw credentials never leave these boundary functions."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from fabricassist.infrastructure.persistence.models import RefreshSession, Tenant, User
from fabricassist.settings import Settings

_passwords = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return _passwords.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _passwords.verify(password_hash, password)
    except (InvalidHashError, VerifyMismatchError):
        return False


def issue_access_token(user: User, settings: Settings) -> str:
    now = datetime.now(UTC)
    return cast(Any, jwt).encode(
        {
            "sub": str(user.id),
            "tenant_id": str(user.tenant_id),
            "role": user.role,
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_minutes),
        },
        settings.access_token_secret,
        algorithm="HS256",
    )


def decode_access_token(token: str, settings: Settings) -> dict[str, str]:
    payload = cast(
        dict[str, Any],
        cast(Any, jwt).decode(token, settings.access_token_secret, algorithms=["HS256"]),
    )
    return {key: str(payload[key]) for key in ("sub", "tenant_id", "role")}


async def register_user(
    session: AsyncSession, *, email: str, password: str, settings: Settings
) -> User:
    tenant = await session.scalar(select(Tenant).where(Tenant.slug == settings.default_tenant_slug))
    if tenant is None:
        raise ValueError("The configured development tenant is unavailable.")
    existing = await session.scalar(
        select(User).where(User.tenant_id == tenant.id, User.email == email)
    )
    if existing is not None:
        raise ValueError("An account with this email already exists.")
    user = User(
        tenant_id=tenant.id, email=email, password_hash=hash_password(password), role="customer"
    )
    session.add(user)
    await session.flush()
    return user


async def authenticate(
    session: AsyncSession, *, email: str, password: str, settings: Settings
) -> User | None:
    tenant = await session.scalar(select(Tenant).where(Tenant.slug == settings.default_tenant_slug))
    if tenant is None:
        return None
    user = await session.scalar(
        select(User).where(User.tenant_id == tenant.id, User.email == email)
    )
    if user is None or not user.is_active:
        return None
    if not await run_in_threadpool(verify_password, user.password_hash, password):
        return None
    return user


async def create_refresh_session(
    session: AsyncSession, user: User, settings: Settings, *, family_id: UUID | None = None
) -> tuple[str, RefreshSession]:
    token = secrets.token_urlsafe(48)
    record = RefreshSession(
        tenant_id=user.tenant_id,
        user_id=user.id,
        family_id=family_id or uuid4(),
        token_hash=_hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
        metadata_json={},
    )
    session.add(record)
    await session.flush()
    return token, record


async def rotate_refresh_session(
    session: AsyncSession, token: str, settings: Settings
) -> tuple[User, str] | None:
    record = await session.scalar(
        select(RefreshSession).where(RefreshSession.token_hash == _hash_token(token))
    )
    if record is None:
        return None
    if record.revoked_at is not None:
        await session.execute(
            update(RefreshSession)
            .where(RefreshSession.family_id == record.family_id)
            .values(revoked_at=datetime.now(UTC))
        )
        return None
    if record.expires_at <= datetime.now(UTC):
        return None
    user = await session.get(User, record.user_id)
    if user is None or not user.is_active:
        return None
    new_token, replacement = await create_refresh_session(
        session, user, settings, family_id=record.family_id
    )
    record.revoked_at = datetime.now(UTC)
    record.replaced_by_id = replacement.id
    return user, new_token


async def revoke_refresh_session(session: AsyncSession, token: str) -> None:
    record = await session.scalar(
        select(RefreshSession).where(RefreshSession.token_hash == _hash_token(token))
    )
    if record is not None and record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
