"""Admin credential API — the headline guarantee: a plaintext secret is never
returned by any endpoint (design spec §6, §13)."""

from __future__ import annotations

from app.security import keys

SECRET = "sk-ant-SUPERSECRET-tokenvalue-1234567890"


async def test_create_lists_masked_and_never_returns_plaintext(auth_client):
    resp = await auth_client.post(
        "/api/admin/credentials",
        json={"provider": "anthropic", "label": "prod", "secret": SECRET},
    )
    assert resp.status_code == 201
    created = resp.json()
    assert SECRET not in resp.text
    assert created["masked_hint"] and created["masked_hint"] != SECRET
    assert "ciphertext" not in created and "secret" not in created

    listed = await auth_client.get("/api/admin/credentials")
    assert listed.status_code == 200
    assert SECRET not in listed.text
    creds = listed.json()["credentials"]
    assert len(creds) == 1
    assert creds[0]["provider"] == "anthropic"
    assert creds[0]["status"] == "active"


async def test_revoke_flips_status_and_audits(auth_client):
    created = (
        await auth_client.post(
            "/api/admin/credentials",
            json={"provider": "openai", "label": "k", "secret": SECRET},
        )
    ).json()
    revoke = await auth_client.post(f"/api/admin/credentials/{created['id']}/revoke")
    assert revoke.status_code == 200

    creds = (await auth_client.get("/api/admin/credentials")).json()["credentials"]
    assert creds[0]["status"] == "revoked"

    audit_resp = await auth_client.get("/api/admin/audit")
    actions = {a["action"] for a in audit_resp.json()["audit"]}
    assert {"credential.create", "credential.revoke"} <= actions
    assert SECRET not in audit_resp.text  # audit never leaks plaintext either


async def test_revoke_unknown_returns_404(auth_client):
    assert (await auth_client.post("/api/admin/credentials/nope/revoke")).status_code == 404


async def test_config_available_reflects_vaulted_provider(auth_client):
    before = (await auth_client.get("/api/config")).json()["llm"]["available"]
    assert "anthropic" not in before

    await auth_client.post(
        "/api/admin/credentials",
        json={"provider": "anthropic", "label": "k", "secret": SECRET},
    )
    after = (await auth_client.get("/api/config")).json()["llm"]["available"]
    assert "anthropic" in after


async def test_rotate_master_key_bumps_version(auth_client):
    await auth_client.post(
        "/api/admin/credentials",
        json={"provider": "anthropic", "label": "k", "secret": SECRET},
    )
    resp = await auth_client.post(
        "/api/admin/credentials/rotate", json={"new_master_key": keys.generate_master_key()}
    )
    assert resp.status_code == 200
    assert resp.json()["key_version"] == 2
    creds = (await auth_client.get("/api/admin/credentials")).json()["credentials"]
    assert creds[0]["key_version"] == 2


async def test_rotate_rejects_bad_key(auth_client):
    resp = await auth_client.post(
        "/api/admin/credentials/rotate", json={"new_master_key": "not-base64!!"}
    )
    assert resp.status_code == 400
