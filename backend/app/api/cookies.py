"""Refresh-token cookie helpers.

The refresh token lives in an httpOnly cookie (Secure in production,
SameSite=Lax), scoped to the auth routes so it is only sent where it's used.
The short-lived access token is returned in the response body instead and sent
back via ``Authorization: Bearer``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Response

if TYPE_CHECKING:
    from app.settings import AppSettings

REFRESH_COOKIE = "autoflow_refresh"
COOKIE_PATH = "/api/auth"
_MAX_AGE_SECONDS = 30 * 24 * 3600  # matches the refresh token TTL


def set_refresh_cookie(response: Response, token: str, settings: "AppSettings") -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.app_env.lower() == "production",
        samesite="lax",
        path=COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
