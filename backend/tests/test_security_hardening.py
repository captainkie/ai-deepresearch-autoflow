"""Regression tests for the pre-M3.5a security hardening pass."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.main import _shutdown, _startup, create_app
from app.security.ratelimit import SlidingWindowLimiter
from app.settings import AppSettings


# --- rate limiting -------------------------------------------------------- #


def test_sliding_window_allows_then_denies():
    lim = SlidingWindowLimiter(max_events=3, window_s=10.0)
    assert lim.allow("k", 0.0)
    assert lim.allow("k", 1.0)
    assert lim.allow("k", 2.0)
    assert not lim.allow("k", 3.0)  # 4th within the window is denied
    # A different key has its own budget.
    assert lim.allow("other", 3.0)
    # Once the window slides past the earliest hits, it opens up again.
    assert lim.allow("k", 11.0)


@pytest.fixture
async def rl_client():
    """A client with rate limiting ENABLED (the default `client` disables it)."""
    settings = AppSettings(
        db_path=":memory:",
        cors_origins=["http://localhost:3000"],
        rate_limit_enabled=True,
    )
    app = create_app()
    await _startup(app, settings)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        yield client
    await _shutdown(app)


async def test_login_is_rate_limited(rl_client):
    codes = []
    for _ in range(12):
        resp = await rl_client.post(
            "/api/auth/login", json={"email": "nobody@x.com", "password": "wrong-guess"}
        )
        codes.append(resp.status_code)
    # 10 attempts/window are allowed (401 invalid creds), then throttled.
    assert 429 in codes
    assert codes.count(401) <= 10


# --- login timing / enumeration ------------------------------------------ #


async def test_login_same_response_for_unknown_and_wrong_password(auth_client):
    # Both an unknown account and a real account with a bad password must return
    # the same 401 (no distinguishing signal).
    unknown = await auth_client.post(
        "/api/auth/login", json={"email": "ghost@x.com", "password": "whatever"}
    )
    wrong = await auth_client.post(
        "/api/auth/login", json={"email": "root@example.com", "password": "wrong-password"}
    )
    assert unknown.status_code == 401
    assert wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


# --- last-superadmin protection ------------------------------------------ #


async def _root_id(auth_client) -> str:
    me = await auth_client.get("/api/auth/me")
    return me.json()["id"]


async def test_cannot_demote_last_superadmin(auth_client):
    uid = await _root_id(auth_client)
    resp = await auth_client.patch(f"/api/admin/users/{uid}", json={"role": "member"})
    assert resp.status_code == 409


async def test_cannot_disable_last_superadmin(auth_client):
    uid = await _root_id(auth_client)
    resp = await auth_client.patch(f"/api/admin/users/{uid}", json={"disabled": True})
    assert resp.status_code == 409


# --- audit attribution ---------------------------------------------------- #


async def test_credential_create_records_actor(auth_client):
    uid = await _root_id(auth_client)
    created = await auth_client.post(
        "/api/admin/credentials",
        json={"provider": "openai", "label": "prod", "secret": "sk-test-1234567890"},
    )
    assert created.status_code == 201

    audit = (await auth_client.get("/api/admin/audit")).json()["audit"]
    creates = [e for e in audit if e["action"] == "credential.create"]
    assert creates, "no credential.create audit entry"
    assert creates[0]["actor_id"] == uid  # attributed to the admin, not NULL
