"""Demo-only maintenance endpoints.

The routes are always mounted but refuse to act unless the server runs as a demo
(``demo_mode``); outside a demo they 404 so they can't be probed in production.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api import API_V1
from app.api.deps import get_app_settings, get_auth_service, get_db
from app.db.database import Database
from app.security.ratelimit import rate_limit
from app.services.demo import reset_demo

if TYPE_CHECKING:
    from app.services.auth_service import AuthService
    from app.settings import AppSettings

router = APIRouter(prefix=f"{API_V1}/demo", tags=["demo"])

RESET_HEADER = "X-Demo-Reset-Token"


@router.post("/reset", dependencies=[Depends(rate_limit(6, 60.0, "demo_reset"))])
async def reset(
    request: Request,
    settings: "AppSettings" = Depends(get_app_settings),
    auth: "AuthService" = Depends(get_auth_service),
    db: Database = Depends(get_db),
) -> dict:
    """Wipe + re-seed the demo DB. Guarded by a shared secret header so only the
    scheduled reset job can call it."""
    if not settings.demo_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    token = settings.demo_reset_token
    provided = request.headers.get(RESET_HEADER)
    if not token or not provided or not secrets.compare_digest(provided, token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid demo reset token")
    await reset_demo(db, auth, settings)
    return {"ok": True}
