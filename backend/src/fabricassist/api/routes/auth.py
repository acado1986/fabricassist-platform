"""Authentication HTTP boundary for Phase 6."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from fabricassist.application.auth import (
    authenticate,
    create_refresh_session,
    issue_access_token,
    register_user,
    revoke_refresh_session,
    rotate_refresh_session,
)
from fabricassist.settings import Settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None


def set_refresh_cookies(response: Response, refresh_token: str, settings: Settings) -> None:
    # A deployed web client may have a different HTTPS origin than the API.
    # Derive cookie attributes from the configured API transport instead of a
    # named environment, while retaining local HTTP development support.
    secure = urlparse(settings.api_public_url).scheme == "https"
    same_site = "none" if secure else "lax"
    response.set_cookie(
        "fabricassist_refresh",
        refresh_token,
        httponly=True,
        secure=secure,
        samesite=same_site,
        path="/api/v1/auth",
    )
    response.set_cookie(
        "fabricassist_csrf",
        "1",
        httponly=False,
        secure=secure,
        samesite=same_site,
        path="/api/v1/auth",
    )


async def get_session() -> AsyncSession:  # replaced by application factory dependency
    raise RuntimeError("Database session dependency was not configured.")


async def get_settings() -> Settings:  # replaced by application factory dependency
    raise RuntimeError("Settings dependency was not configured.")


@router.post("/register", response_model=SessionResponse, status_code=201)
async def register(
    credentials: Credentials,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionResponse:
    try:
        user = await register_user(
            session,
            email=credentials.email.lower(),
            password=credentials.password,
            settings=settings,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=409, detail="Registration could not be completed."
        ) from error
    refresh_token, _ = await create_refresh_session(session, user, settings)
    await session.commit()
    set_refresh_cookies(response, refresh_token, settings)
    return SessionResponse(access_token=issue_access_token(user, settings))


@router.post("/login", response_model=SessionResponse)
async def login(
    credentials: Credentials,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionResponse:
    user = await authenticate(
        session, email=credentials.email.lower(), password=credentials.password, settings=settings
    )
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    refresh_token, _ = await create_refresh_session(session, user, settings)
    await session.commit()
    set_refresh_cookies(response, refresh_token, settings)
    return SessionResponse(access_token=issue_access_token(user, settings))


@router.post("/refresh", response_model=SessionResponse)
async def refresh(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    refresh_cookie: Annotated[str | None, Cookie(alias="fabricassist_refresh")] = None,
    csrf_cookie: Annotated[str | None, Cookie(alias="fabricassist_csrf")] = None,
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> SessionResponse:
    if refresh_cookie is not None and (csrf_cookie != "1" or csrf_header != "1"):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")
    if refresh_cookie is None:
        raise HTTPException(status_code=401, detail="Session refresh failed.")
    rotated = await rotate_refresh_session(session, refresh_cookie, settings)
    if rotated is None:
        await session.commit()
        raise HTTPException(status_code=401, detail="Session refresh failed.")
    user, refresh_token = rotated
    await session.commit()
    set_refresh_cookies(response, refresh_token, settings)
    return SessionResponse(access_token=issue_access_token(user, settings))


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    refresh_cookie: Annotated[str | None, Cookie(alias="fabricassist_refresh")] = None,
) -> Response:
    if refresh_cookie is not None:
        await revoke_refresh_session(session, refresh_cookie)
        await session.commit()
    response.delete_cookie("fabricassist_refresh", path="/api/v1/auth")
    response.delete_cookie("fabricassist_csrf", path="/api/v1/auth")
    return Response(status_code=204)
