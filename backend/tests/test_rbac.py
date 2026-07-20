"""RBAC matrix — every role against the sensitive actions, plus disabled lockout.

Roles are resolved from the DB row on each request (not the token), so a promotion
or a disable takes effect immediately even for an already-issued access token.
"""

from __future__ import annotations

from app.security import keys

SUPER = {"email": "root@example.com", "name": "Root", "password": "supersecret1"}


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, email: str) -> dict:
    resp = await client.post(
        "/api/auth/register", json={"email": email, "name": email, "password": "password1"}
    )
    return resp.json()


async def test_rbac_matrix(client):
    setup = (await client.post("/api/setup", json=SUPER)).json()
    root_id, super_tok = setup["user"]["id"], setup["access_token"]

    member = await _register(client, "member@example.com")
    admin = await _register(client, "admin@example.com")
    viewer = await _register(client, "viewer@example.com")
    member_tok, admin_tok, viewer_tok = (
        member["access_token"],
        admin["access_token"],
        viewer["access_token"],
    )

    # Superadmin sets roles.
    assert (
        await client.patch(
            f"/api/admin/users/{admin['user']['id']}", json={"role": "admin"}, headers=_h(super_tok)
        )
    ).status_code == 200
    assert (
        await client.patch(
            f"/api/admin/users/{viewer['user']['id']}",
            json={"role": "viewer"},
            headers=_h(super_tok),
        )
    ).status_code == 200

    # --- unauthenticated is rejected everywhere it matters ---
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.post("/api/runs", json={"query": "x"})).status_code == 401
    assert (await client.get("/api/admin/credentials")).status_code == 401

    # --- viewer: read-only, cannot create runs ---
    assert (
        await client.post("/api/runs", json={"query": "x"}, headers=_h(viewer_tok))
    ).status_code == 403

    # --- member: creates runs; cannot touch admin surfaces ---
    created = await client.post(
        "/api/runs",
        json={"query": "brand X", "config": {"llm_provider": "mock", "search_provider": "mock"}},
        headers=_h(member_tok),
    )
    assert created.status_code == 201
    member_run = created.json()["run_id"]
    assert (await client.get("/api/admin/credentials", headers=_h(member_tok))).status_code == 403
    assert (
        await client.post("/api/config", json={"llm_provider": "mock"}, headers=_h(member_tok))
    ).status_code == 403

    # --- ownership: a different member can't read the run (hidden as 404) ---
    other = await _register(client, "other@example.com")
    assert (
        await client.get(f"/api/runs/{member_run}", headers=_h(other["access_token"]))
    ).status_code == 404
    assert (await client.get(f"/api/runs/{member_run}", headers=_h(member_tok))).status_code == 200
    assert (await client.get(f"/api/runs/{member_run}", headers=_h(admin_tok))).status_code == 200

    # --- admin manages creds but cannot rotate the master key (superadmin only) ---
    assert (await client.get("/api/admin/credentials", headers=_h(admin_tok))).status_code == 200
    assert (
        await client.post(
            "/api/admin/credentials/rotate",
            json={"new_master_key": keys.generate_master_key()},
            headers=_h(admin_tok),
        )
    ).status_code == 403
    assert (
        await client.post(
            "/api/admin/credentials/rotate",
            json={"new_master_key": keys.generate_master_key()},
            headers=_h(super_tok),
        )
    ).status_code == 200

    # --- an admin cannot manage a superadmin ---
    assert (
        await client.patch(
            f"/api/admin/users/{root_id}", json={"disabled": True}, headers=_h(admin_tok)
        )
    ).status_code == 403

    # --- disabling a user locks them out immediately, even with a live token ---
    assert (
        await client.patch(
            f"/api/admin/users/{member['user']['id']}",
            json={"disabled": True},
            headers=_h(super_tok),
        )
    ).status_code == 200
    assert (await client.get("/api/auth/me", headers=_h(member_tok))).status_code == 401
    assert (
        await client.post("/api/runs", json={"query": "x"}, headers=_h(member_tok))
    ).status_code == 401
