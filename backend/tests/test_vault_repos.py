"""CredentialRepo + AuditRepo — encrypted-at-rest storage and the audit trail."""

from __future__ import annotations

import json

import pytest

from app.db.database import Database
from app.db.repositories import AuditRepo, CredentialRepo


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.init()
    try:
        yield database
    finally:
        await database.close()


async def test_schema_has_security_tables(db):
    rows = await db.fetchall("SELECT name FROM sqlite_master WHERE type = 'table'")
    names = {row["name"] for row in rows}
    assert {"provider_credentials", "audit_log"} <= names


def _cred(**overrides):
    base = dict(
        id="c1",
        provider="anthropic",
        label="prod key",
        ciphertext=b"\x00\x01\x02\xff",
        nonce=b"\x10" * 12,
        key_version=1,
        masked_hint="sk-a…wxyz",
        created_by="u1",
        created_at="2026-07-20T00:00:01+00:00",
    )
    base.update(overrides)
    return base


async def test_credential_create_get_blob_roundtrip(db):
    repo = CredentialRepo(db)
    await repo.create(**_cred())
    row = await repo.get("c1")
    assert row is not None
    assert bytes(row["ciphertext"]) == b"\x00\x01\x02\xff"
    assert bytes(row["nonce"]) == b"\x10" * 12
    assert row["masked_hint"] == "sk-a…wxyz"
    assert row["status"] == "active"
    assert row["last_used_at"] is None
    assert await repo.get("nope") is None


async def test_credential_list_and_active_for_provider(db):
    repo = CredentialRepo(db)
    await repo.create(**_cred(id="c1", created_at="2026-07-20T00:00:01+00:00"))
    await repo.create(**_cred(id="c2", created_at="2026-07-20T00:00:02+00:00"))
    await repo.create(**_cred(id="c3", provider="openai", created_at="2026-07-20T00:00:03+00:00"))

    # Newest first.
    assert [r["id"] for r in await repo.list()] == ["c3", "c2", "c1"]
    assert [r["id"] for r in await repo.list("anthropic")] == ["c2", "c1"]

    # Revoked credentials drop out of active_for_provider.
    await repo.set_status("c2", "revoked")
    assert [r["id"] for r in await repo.active_for_provider("anthropic")] == ["c1"]


async def test_credential_set_last_used_and_rotate_ciphertext(db):
    repo = CredentialRepo(db)
    await repo.create(**_cred())

    await repo.set_last_used("c1", "2026-07-20T01:00:00+00:00")
    assert (await repo.get("c1"))["last_used_at"] == "2026-07-20T01:00:00+00:00"

    await repo.update_ciphertext("c1", ciphertext=b"\xaa\xbb", nonce=b"\x20" * 12, key_version=2)
    row = await repo.get("c1")
    assert bytes(row["ciphertext"]) == b"\xaa\xbb"
    assert row["key_version"] == 2


async def test_audit_append_and_list_newest_first(db):
    audit = AuditRepo(db)
    await audit.append(
        id="a1",
        actor_id="u1",
        action="credential.create",
        target_type="credential",
        target_id="c1",
        meta={"provider": "anthropic"},
        created_at="2026-07-20T00:00:01+00:00",
    )
    await audit.append(
        id="a2",
        actor_id="u1",
        action="credential.revoke",
        target_type="credential",
        target_id="c1",
        meta=None,
        created_at="2026-07-20T00:00:02+00:00",
    )
    rows = await audit.list()
    assert [r["id"] for r in rows] == ["a2", "a1"]
    assert rows[0]["meta_json"] is None
    assert json.loads(rows[1]["meta_json"]) == {"provider": "anthropic"}
