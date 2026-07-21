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
        # Isolate tests from the developer's backend/.env (e.g. real GOOGLE_* keys)
        # so results don't depend on local secrets.
        _env_file=None,
        db_path=":memory:",
        cors_origins=["http://localhost:3000"],
        default_language="en",
        default_require_plan_approval=True,
        rate_limit_enabled=False,
        # Force OAuth unconfigured regardless of any GOOGLE_* in the environment,
        # so google-config tests are deterministic.
        google_client_id=None,
        google_client_secret=None,
        google_redirect_uri=None,
    )


@pytest.fixture
async def client(app_settings):
    app = create_app()
    await _startup(app, app_settings)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as http_client:
        yield http_client
    await _shutdown(app)


@pytest.fixture
async def auth_client(client):
    """A ``client`` authenticated as the first superadmin (via first-run setup).

    Superadmin passes every role check and owns the runs it creates, so it's the
    simplest identity for tests that just need to be past the auth wall. The Bearer
    token is set as a default header on the client.
    """
    resp = await client.post(
        "/api/v1/setup",
        json={"email": "root@example.com", "name": "Root", "password": "supersecret1"},
    )
    client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
    return client
