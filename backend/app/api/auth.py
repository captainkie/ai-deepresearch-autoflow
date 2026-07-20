"""Auth routes: register, password login, logout, refresh, and current user.

Login/register/refresh return ``{ user, access_token }`` in the body and set the
rotating refresh token as an httpOnly cookie. Protected routes read the access
token from ``Authorization: Bearer``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.api.cookies import REFRESH_COOKIE, clear_refresh_cookie, set_refresh_cookie
from app.api.deps import get_app_settings, get_auth_service
from app.security.rbac import get_current_user
from app.services.auth_service import AuthService, EmailExistsError

if TYPE_CHECKING:
    from app.settings import AppSettings

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
