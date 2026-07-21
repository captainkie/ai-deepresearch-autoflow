"""Auth routes — register/login/me, refresh rotation, logout."""

from __future__ import annotations

SUPERADMIN = {"email": "boss@example.com", "name": "Boss", "password": "supersecret1"}


async def _bootstrap(client):
    """Create the first superadmin so the instance is out of setup mode."""
    await client.post("/api/v1/setup", json=SUPERADMIN)


async def test_register_login_me_flow(client):
    await _bootstrap(client)
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "mem@example.com", "name": "Mem", "password": "password1"},
    )
    assert reg.status_code == 201
    assert reg.json()["user"]["role"] == "member"
    access = reg.json()["access_token"]

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["email"] == "mem@example.com"
    assert "password_hash" not in me.json()

    # No / bad token → 401.
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    assert (
        await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nope"})
    ).status_code == 401


async def test_login_wrong_password_rejected(client):
    await _bootstrap(client)
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "boss@example.com", "password": "wrong"}
    )
    assert resp.status_code == 401


async def test_login_then_refresh_rotates(client):
    await _bootstrap(client)
    login = await client.post(
        "/api/v1/auth/login", json={"email": "boss@example.com", "password": "supersecret1"}
    )
    assert login.status_code == 200
    refreshed = await client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]


async def test_logout_then_refresh_fails(client):
    await _bootstrap(client)
    await client.post(
        "/api/v1/auth/login", json={"email": "boss@example.com", "password": "supersecret1"}
    )
    assert (await client.post("/api/v1/auth/logout")).status_code == 200
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_duplicate_registration_conflicts(client):
    await _bootstrap(client)
    body = {"email": "dup@example.com", "name": "Dup", "password": "password1"}
    assert (await client.post("/api/v1/auth/register", json=body)).status_code == 201
    assert (await client.post("/api/v1/auth/register", json=body)).status_code == 409
