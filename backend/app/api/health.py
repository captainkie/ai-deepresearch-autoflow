"""Health + about endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from app.api import API_V1
from app.__about__ import ACKNOWLEDGEMENTS, APP_NAME, AUTHORS, LICENSE, ORG, VERSION
from app.api.deps import get_app_settings
from app.api.schemas_api import AboutResponse, HealthResponse

if TYPE_CHECKING:
    from app.settings import AppSettings

router = APIRouter(prefix=API_V1, tags=["health"])


@router.get("/health")
async def health(settings: "AppSettings" = Depends(get_app_settings)) -> HealthResponse:
    return HealthResponse(status="ok", version=VERSION, demo_mode=settings.demo_mode)


@router.get("/about")
async def about() -> AboutResponse:
    return AboutResponse(
        app=APP_NAME,
        version=VERSION,
        license=LICENSE,
        org=ORG,
        authors=AUTHORS,
        acknowledgements=ACKNOWLEDGEMENTS,
    )
