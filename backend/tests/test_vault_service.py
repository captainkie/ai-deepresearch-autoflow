"""VaultService — encrypt-on-write, decrypt-at-use, and the plaintext-never-out rule."""

from __future__ import annotations

import base64
import json
from itertools import count

import pytest

from app.db.database import Database
from app.db.repositories import AuditRepo, CredentialRepo
from app.security import keys
from app.security.crypto import Vault
from app.services.vault_service import VaultService

SECRET = "sk-secret-abcdefghijklmnop"


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.init()
    try:
        yield database
    finally:
        await database.close()


def make_service(db: Database) -> VaultService:
    ids = count(1)
    times = count(1)
    return VaultService(
        credentials=CredentialRepo(db),
        audit=AuditRepo(db),
        vault=Vault(base64.b64decode(keys.generate_master_key())),
        now=lambda: f"2026-07-20T00:00:{next(times):02d}+00:00",
        new_id=lambda: f"id{next(ids)}",
    )


async def test_add_credential_returns_metadata_only(db):
    svc = make_service(db)
    meta = await svc.add_credential(
        provider="anthropic", label="prod", plaintext=SECRET, actor_id="u1"
    )
    # Never leak secret material through the write response.
    assert SECRET not in json.dumps(meta)
    assert "ciphertext" not in meta and "nonce" not in meta
    assert meta["masked_hint"] and meta["masked_hint"] != SECRET
    assert meta["provider"] == "anthropic" and meta["status"] == "active"


async def test_resolve_decrypts_active_and_records_use(db):
    svc = make_service(db)
    await svc.add_credential(provider="anthropic", label="k", plaintext=SECRET, actor_id="u1")
    assert await svc.resolve("anthropic") == SECRET
    # last_used recorded + audited.
    creds = await svc.list_credentials("anthropic")
    assert creds[0]["last_used_at"] is not None
    actions = [a["action"] for a in await svc.list_audit()]
    assert "credential.use" in actions and "credential.create" in actions
    assert await svc.resolve("openai") is None  # no cred for provider


async def test_resolve_prefers_newest_active(db):
    svc = make_service(db)
    await svc.add_credential(provider="p", label="old", plaintext="OLD-KEY", actor_id="u1")
    await svc.add_credential(provider="p", label="new", plaintext="NEW-KEY", actor_id="u1")
    assert await svc.resolve("p") == "NEW-KEY"


async def test_revoked_credential_is_not_resolved(db):
    svc = make_service(db)
    meta = await svc.add_credential(provider="p", label="k", plaintext=SECRET, actor_id="u1")
    assert await svc.revoke(meta["id"], actor_id="u1") is True
    assert await svc.resolve("p") is None
    assert "credential.revoke" in [a["action"] for a in await svc.list_audit()]


async def test_expired_credential_is_not_resolved(db):
    svc = make_service(db)
    await svc.add_credential(
        provider="p",
        label="k",
        plaintext=SECRET,
        actor_id="u1",
        expires_at="2020-01-01T00:00:00+00:00",
    )
    assert await svc.resolve("p") is None


async def test_rotate_master_key_reencrypts_and_bumps_version(db):
    svc = make_service(db)
    await svc.add_credential(provider="p", label="k", plaintext=SECRET, actor_id="u1")
    new_key = base64.b64decode(keys.generate_master_key())
    version = await svc.rotate_master_key(new_key, actor_id="admin")
    assert version == 2
    # Still resolvable under the new key; version bumped.
    assert await svc.resolve("p") == SECRET
    assert (await svc.list_credentials("p"))[0]["key_version"] == 2
    assert "credential.rotate" in [a["action"] for a in await svc.list_audit()]


async def test_list_credentials_never_serializes_plaintext(db):
    svc = make_service(db)
    await svc.add_credential(provider="anthropic", label="k", plaintext=SECRET, actor_id="u1")
    await svc.resolve("anthropic")  # forces decrypt path too
    assert SECRET not in json.dumps(await svc.list_credentials())
    assert SECRET not in json.dumps(await svc.list_audit())
