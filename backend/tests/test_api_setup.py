"""First-run setup endpoint — replay-guarded superadmin onboarding."""

from __future__ import annotations

SETUP = {"email": "boss@example.com", "name": "Boss", "password": "supersecret1"}


async def test_status_reports_needs_setup_when_empty(client):
    assert (await client.get("/api/setup/status")).json()["needs_setup"] is True


async def test_setup_creates_superadmin_and_is_replay_guarded(client):
    resp = await client.post("/api/setup", json=SETUP)
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["role"] == "superadmin"
    assert body["user"]["email"] == "boss@example.com"
    assert body["access_token"]

    # Setup mode is over.
    assert (await client.get("/api/setup/status")).json()["needs_setup"] is False

    # A second attempt can never seize the instance.
    replay = await client.post(
        "/api/setup",
        json={"email": "evil@example.com", "name": "Evil", "password": "supersecret1"},
    )
    assert replay.status_code == 409


async def test_setup_rejects_short_password(client):
    resp = await client.post(
        "/api/setup", json={"email": "a@b.com", "name": "A", "password": "short"}
    )
    assert resp.status_code == 422
