"""Health + about endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import API_V1
from app.__about__ import ACKNOWLEDGEMENTS, APP_NAME, AUTHORS, LICENSE, ORG, VERSION
from app.api.schemas_api import AboutResponse, HealthResponse

router = APIRouter(prefix=API_V1, tags=["health"])


@router.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=VERSION)


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
