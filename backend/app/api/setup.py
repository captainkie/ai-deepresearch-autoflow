"""First-run setup — create the initial superadmin (Strapi-style).

On a fresh install (`users` empty) the app is in setup mode. ``POST /api/setup``
creates the first user as ``superadmin`` and is **guarded to run only when zero
users exist** (409 otherwise), so it can never be replayed to seize an instance.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.cookies import set_refresh_cookie
from app.api.deps import get_app_settings, get_auth_service, get_db
from app.db.database import Database
from app.db.repositories import SettingsRepo
from app.security.ratelimit import rate_limit
from app.services.auth_service import AuthService

if TYPE_CHECKING:
    from app.settings import AppSettings

router = APIRouter(prefix="/api/setup", tags=["setup"])

# Serialize first-run setup so two concurrent requests can't both pass the
# "zero users" check and each create a superadmin (single-process app).
_setup_lock = asyncio.Lock()


class SetupRequest(BaseModel):
    email: str = Field(min_length=3)
    name: str = Field(min_length=1)
    password: str = Field(min_length=8)


@router.get("/status")
async def setup_status(auth: AuthService = Depends(get_auth_service)) -> dict:
    return {"needs_setup": (await auth.count_users()) == 0}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(5, 60.0, "setup"))],
)
async def run_setup(
    body: SetupRequest,
    response: Response,
    settings: "AppSettings" = Depends(get_app_settings),
    auth: AuthService = Depends(get_auth_service),
    db: Database = Depends(get_db),
) -> dict:
    async with _setup_lock:
        if await auth.count_users() > 0:
            raise HTTPException(status.HTTP_409_CONFLICT, "setup already completed")
        user = await auth.register(
            email=body.email, name=body.name, password=body.password, role="superadmin"
        )
        await SettingsRepo(db).set("setup_completed", True)
    row = await auth.authenticate(body.email, body.password)
    assert row is not None
    access, refresh = await auth.issue_tokens(row)
    set_refresh_cookie(response, refresh, settings)
    return {"user": user, "access_token": access}
