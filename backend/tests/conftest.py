"""Shared fixtures for the HTTP API tests.

``client`` builds the FastAPI app against an in-memory SQLite DB and serves it
through ``httpx.ASGITransport`` — no network, no real DB file. Because
``ASGITransport`` does not run ASGI lifespan events, we drive ``_startup`` /
``_shutdown`` from ``app.main`` directly.
"""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.main import _shutdown, _startup, create_app
from app.settings import AppSettings


@pytest.fixture
def app_settings() -> AppSettings:
    return AppSettings(
        db_path=":memory:",
        cors_origins=["http://localhost:3000"],
        default_language="en",
        default_require_plan_approval=True,
    )


@pytest.fixture
async def client(app_settings):
    app = create_app()
    await _startup(app, app_settings)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as http_client:
        yield http_client
    await _shutdown(app)
