"""Auth routes: register, password login, logout, refresh, and current user.

Login/register/refresh return ``{ user, access_token }`` in the body and set the
rotating refresh token as an httpOnly cookie. Protected routes read the access
token from ``Authorization: Bearer``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.api.cookies import REFRESH_COOKIE, clear_refresh_cookie, set_refresh_cookie
from app.api.deps import get_app_settings, get_auth_service, get_oauth_service
from app.security.rbac import get_current_user
from app.services.auth_service import AuthService, EmailExistsError
from app.services.oauth_service import GoogleOAuthService, OAuthError

if TYPE_CHECKING:
    from app.settings import AppSettings

router = APIRouter(prefix="/api/auth", tags=["auth"])

OAUTH_COOKIE = "autoflow_oauth"
_OAUTH_COOKIE_PATH = "/api/auth/google"


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3)
    name: str = Field(min_length=1)
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


async def _session_response(
    auth: AuthService, user: aiosqlite.Row, response: Response, settings: "AppSettings"
) -> dict:
    access, refresh = await auth.issue_tokens(user, user_agent=None)
    set_refresh_cookie(response, refresh, settings)
    return {"user": AuthService.public(user), "access_token": access}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    response: Response,
    settings: "AppSettings" = Depends(get_app_settings),
    auth: AuthService = Depends(get_auth_service),
) -> dict:
    # Self-registration creates a `member`; admins manage roles afterward.
    try:
        await auth.register(email=body.email, name=body.name, password=body.password, role="member")
    except EmailExistsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered") from exc
    row = await auth.authenticate(body.email, body.password)
    assert row is not None
    return await _session_response(auth, row, response, settings)


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    settings: "AppSettings" = Depends(get_app_settings),
    auth: AuthService = Depends(get_auth_service),
) -> dict:
    row = await auth.authenticate(body.email, body.password)
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    return await _session_response(auth, row, response, settings)


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    settings: "AppSettings" = Depends(get_app_settings),
    auth: AuthService = Depends(get_auth_service),
) -> dict:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no refresh token")
    rotated = await auth.rotate_refresh(token, user_agent=None)
    if rotated is None:
        clear_refresh_cookie(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token")
    access, new_refresh, user = rotated
    set_refresh_cookie(response, new_refresh, settings)
    return {"user": AuthService.public(user), "access_token": access}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
) -> dict:
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        await auth.logout(token)
    clear_refresh_cookie(response)
    return {"ok": True}


@router.get("/me")
async def me(user: aiosqlite.Row = Depends(get_current_user)) -> dict:
    return AuthService.public(user)


@router.get("/google/start")
async def google_start(
    response: Response,
    settings: "AppSettings" = Depends(get_app_settings),
    oauth: GoogleOAuthService | None = Depends(get_oauth_service),
) -> dict:
    if oauth is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "google oauth is not configured")
    url, state, verifier = oauth.start()
    # Bind the PKCE verifier + CSRF state to this browser for the callback.
    response.set_cookie(
        OAUTH_COOKIE,
        f"{state}:{verifier}",
        max_age=600,
        httponly=True,
        secure=settings.app_env.lower() == "production",
        samesite="lax",
        path=_OAUTH_COOKIE_PATH,
    )
    return {"auth_url": url}


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str,
    state: str,
    settings: "AppSettings" = Depends(get_app_settings),
    auth: AuthService = Depends(get_auth_service),
    oauth: GoogleOAuthService | None = Depends(get_oauth_service),
) -> RedirectResponse:
    if oauth is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "google oauth is not configured")
    stored = request.cookies.get(OAUTH_COOKIE)
    if not stored or ":" not in stored:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "missing oauth state")
    expected_state, verifier = stored.split(":", 1)
    if state != expected_state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "oauth state mismatch")
    try:
        profile = await oauth.complete(code, verifier)
    except OAuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    user = await auth.link_or_create_google_user(
        sub=profile["sub"], email=profile["email"], name=profile["name"]
    )
    _, refresh = await auth.issue_tokens(user)
    # The browser lands here from Google; set the session cookie and bounce to the app.
    redirect = RedirectResponse(url=settings.frontend_url, status_code=status.HTTP_302_FOUND)
    set_refresh_cookie(redirect, refresh, settings)
    redirect.delete_cookie(OAUTH_COOKIE, path=_OAUTH_COOKIE_PATH)
    return redirect
