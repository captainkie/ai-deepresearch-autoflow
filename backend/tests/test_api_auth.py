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


# --- Input validation (Pydantic: EmailStr + shared password/name constraints) --- #


async def test_setup_validates_email_and_password(client):
    # A malformed email is rejected at the schema boundary (422), not stored.
    bad_email = await client.post(
        "/api/v1/setup",
        json={"email": "not-an-email", "name": "Boss", "password": "supersecret1"},
    )
    assert bad_email.status_code == 422
    # A password shorter than 8 chars is rejected.
    short_pw = await client.post(
        "/api/v1/setup",
        json={"email": "boss@example.com", "name": "Boss", "password": "short"},
    )
    assert short_pw.status_code == 422
    # Still in setup mode — neither invalid request created a user.
    assert (await client.get("/api/v1/setup/status")).json()["needs_setup"] is True


async def test_register_validates_email_password_and_name(client):
    await _bootstrap(client)
    invalid = [
        {"email": "bad", "name": "X", "password": "password1"},  # bad email
        {"email": "x@example.com", "name": "X", "password": "short"},  # short pw
        {"email": "y@example.com", "name": "   ", "password": "password1"},  # blank name
    ]
    for body in invalid:
        resp = await client.post("/api/v1/auth/register", json=body)
        assert resp.status_code == 422, body


async def test_login_rejects_malformed_email(client):
    await _bootstrap(client)
    # A non-email is a schema error (422), distinct from wrong credentials (401).
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "notanemail", "password": "supersecret1"}
    )
    assert resp.status_code == 422
