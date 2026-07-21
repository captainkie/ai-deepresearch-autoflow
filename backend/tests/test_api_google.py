"""Google OAuth routes — end-to-end with Google mocked, plus config/state guards."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.main import _shutdown, _startup, create_app
from app.services.oauth_service import (
    TOKEN_ENDPOINT,
    USERINFO_ENDPOINT,
    GoogleOAuthService,
)
from app.settings import AppSettings

VERIFIED = {
    "sub": "g-777",
    "email": "oauth@example.com",
    "email_verified": True,
    "name": "OAuth User",
}


def _mock_google() -> GoogleOAuthService:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(TOKEN_ENDPOINT):
            return httpx.Response(200, json={"access_token": "ya29.mock"})
        if url.startswith(USERINFO_ENDPOINT):
            return httpx.Response(200, json=VERIFIED)
        return httpx.Response(404)

    return GoogleOAuthService(
        client_id="cid",
        client_secret="sec",
        redirect_uri="http://localhost:8000/api/v1/auth/google/callback",
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


@pytest.fixture
async def google_client():
    settings = AppSettings(
        db_path=":memory:",
        cors_origins=["http://localhost:3000"],
        default_language="en",
        default_require_plan_approval=True,
    )
    settings.google_client_id = "cid"
    settings.google_client_secret = "sec"
    settings.google_redirect_uri = "http://localhost:8000/api/v1/auth/google/callback"

    app = create_app()
    await _startup(app, settings)
    app.state.oauth_service = _mock_google()  # replace real Google with a mock
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as http_client:
        yield http_client
    await _shutdown(app)


async def test_google_start_503_when_unconfigured():
    # Self-contained + force oauth off, so it's immune to any GOOGLE_* the
    # developer has in backend/.env / the environment.
    settings = AppSettings(
        _env_file=None, db_path=":memory:", cors_origins=["http://localhost:3000"]
    )
    app = create_app()
    await _startup(app, settings)
    app.state.oauth_service = None
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        assert (await client.get("/api/v1/auth/google/start")).status_code == 503
    await _shutdown(app)


async def test_google_login_end_to_end(google_client):
    start = await google_client.get("/api/v1/auth/google/start")
    assert start.status_code == 200
    assert start.json()["auth_url"].startswith("https://accounts.google.com")

    raw = google_client.cookies.get("autoflow_oauth")
    assert raw is not None
    state = raw.split(":", 1)[0]

    callback = await google_client.get(
        f"/api/v1/auth/google/callback?code=abc&state={state}", follow_redirects=False
    )
    assert callback.status_code == 302

    # Session established via the refresh cookie → mint an access token → /me works.
    refreshed = await google_client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    access = refreshed.json()["access_token"]
    me = await google_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["email"] == "oauth@example.com"
    assert me.json()["role"] == "member"


async def test_google_callback_rejects_state_mismatch(google_client):
    await google_client.get("/api/v1/auth/google/start")
    callback = await google_client.get(
        "/api/v1/auth/google/callback?code=abc&state=WRONG", follow_redirects=False
    )
    assert callback.status_code == 400
