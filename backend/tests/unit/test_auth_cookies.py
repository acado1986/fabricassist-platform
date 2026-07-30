from types import SimpleNamespace
from typing import cast

from starlette.responses import Response

from fabricassist.api.routes.auth import set_refresh_cookies
from fabricassist.settings import Settings


def test_https_refresh_cookies_support_a_separate_web_origin() -> None:
    response = Response()

    set_refresh_cookies(
        response,
        "refresh-token",
        cast(Settings, SimpleNamespace(api_public_url="https://api.example.test")),
    )

    cookies = response.headers.getlist("set-cookie")
    assert len(cookies) == 2
    assert all("; HttpOnly" in cookie or "fabricassist_csrf=" in cookie for cookie in cookies)
    assert all("; SameSite=none" in cookie for cookie in cookies)
    assert all("; Secure" in cookie for cookie in cookies)


def test_development_refresh_cookies_remain_usable_over_local_http() -> None:
    response = Response()

    set_refresh_cookies(
        response,
        "refresh-token",
        cast(Settings, SimpleNamespace(api_public_url="http://localhost:8000")),
    )

    cookies = response.headers.getlist("set-cookie")
    assert all("; SameSite=lax" in cookie for cookie in cookies)
    assert not any("; Secure" in cookie for cookie in cookies)
