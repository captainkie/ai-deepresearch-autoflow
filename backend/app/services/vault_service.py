"""The credential vault service — the only place plaintext secrets are handled.

Secrets are encrypted on write (``add_credential``) and decrypted only at call
time (``resolve``, used by the provider layer). Reads for humans go through
``list_credentials`` / ``_public`` which return **metadata + a masked hint only**
— never ciphertext, nonce, or plaintext. Every mutation and every use writes an
``audit_log`` row.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import aiosqlite

from app.db.repositories import AuditRepo, CredentialRepo
from app.security.crypto import Vault, masked_hint


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class VaultService:
    def __init__(
        self,
        *,
        credentials: CredentialRepo,
        audit: AuditRepo,
        vault: Vault,
        key_version: int = 1,
        now: Callable[[], str] | None = None,
        new_id: Callable[[], str] | None = None,
    ) -> None:
        self._creds = credentials
        self._audit = audit
        self._vault = vault
        self._key_version = key_version
        self._now = now or _utc_now_iso
        self._new_id = new_id or (lambda: uuid4().hex)

    # --- write / manage (metadata only out) --------------------------------- #

    async def add_credential(
        self,
        *,
        provider: str,
        label: str,
        plaintext: str,
        actor_id: str | None,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        ciphertext, nonce = self._vault.encrypt(plaintext)
        cred_id = self._new_id()
        ts = self._now()
        await self._creds.create(
            id=cred_id,
            provider=provider,
            label=label,
            ciphertext=ciphertext,
            nonce=nonce,
            key_version=self._key_version,
            masked_hint=masked_hint(plaintext),
            created_by=actor_id,
            created_at=ts,
            expires_at=expires_at,
        )
        await self._log(actor_id, "credential.create", cred_id, {"provider": provider})
        row = await self._creds.get(cred_id)
        assert row is not None
        return self._public(row)

    async def list_credentials(self, provider: str | None = None) -> list[dict[str, Any]]:
        return [self._public(r) for r in await self._creds.list(provider)]

    async def revoke(self, cred_id: str, *, actor_id: str | None) -> bool:
        row = await self._creds.get(cred_id)
        if row is None:
            return False
        await self._creds.set_status(cred_id, "revoked")
        await self._log(actor_id, "credential.revoke", cred_id, {"provider": row["provider"]})
        return True

    async def list_audit(self, limit: int = 200) -> list[dict[str, Any]]:
        return [dict(r) for r in await self._audit.list(limit)]

    async def active_providers(self) -> set[str]:
        """Providers with at least one active, non-expired credential."""
        return {
            row["provider"]
            for row in await self._creds.list()
            if row["status"] == "active" and not self._is_expired(row["expires_at"])
        }

    # --- use (plaintext out — provider layer only, never serialized) -------- #

    async def resolve(self, provider: str) -> str | None:
        for row in await self._creds.active_for_provider(provider):
            if self._is_expired(row["expires_at"]):
                continue
            plaintext = self._vault.decrypt(bytes(row["ciphertext"]), bytes(row["nonce"]))
            await self._creds.set_last_used(row["id"], self._now())
            await self._log(None, "credential.use", row["id"], {"provider": provider})
            return plaintext
        return None

    # --- master-key rotation ------------------------------------------------ #

    async def rotate_master_key(self, new_key: bytes, *, actor_id: str | None) -> int:
        """Re-encrypt every credential under ``new_key`` and bump the key version.

        Decrypts everything first so a bad ciphertext aborts before any write
        (all-or-nothing at the app level).
        """
        new_vault = Vault(new_key)
        rows = await self._creds.all()
        plaintexts = {
            row["id"]: self._vault.decrypt(bytes(row["ciphertext"]), bytes(row["nonce"]))
            for row in rows
        }
        new_version = self._key_version + 1
        for cred_id, plaintext in plaintexts.items():
            ciphertext, nonce = new_vault.encrypt(plaintext)
            await self._creds.update_ciphertext(
                cred_id, ciphertext=ciphertext, nonce=nonce, key_version=new_version
            )
        self._vault = new_vault
        self._key_version = new_version
        await self._log(
            actor_id, "credential.rotate", None, {"key_version": new_version, "count": len(rows)}
        )
        return new_version

    # --- helpers ------------------------------------------------------------ #

    @staticmethod
    def _public(row: aiosqlite.Row) -> dict[str, Any]:
        """Human-facing view — metadata + masked hint ONLY (no secret material)."""
        return {
            "id": row["id"],
            "provider": row["provider"],
            "label": row["label"],
            "masked_hint": row["masked_hint"],
            "status": row["status"],
            "key_version": row["key_version"],
            "created_by": row["created_by"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "last_used_at": row["last_used_at"],
        }

    def _is_expired(self, expires_at: str | None) -> bool:
        if not expires_at:
            return False
        try:
            exp = datetime.fromisoformat(expires_at)
            now = datetime.fromisoformat(self._now())
            # A naive stored timestamp can't be compared to an aware one (raises
            # TypeError). Assume UTC for a naive expiry so a client that stored a
            # tz-less value doesn't break key resolution.
            if exp.tzinfo is None and now.tzinfo is not None:
                exp = exp.replace(tzinfo=now.tzinfo)
            return exp <= now
        except (ValueError, TypeError):
            return False

    async def _log(
        self, actor_id: str | None, action: str, target_id: str | None, meta: dict[str, Any] | None
    ) -> None:
        await self._audit.append(
            id=self._new_id(),
            actor_id=actor_id,
            action=action,
            target_type="credential",
            target_id=target_id,
            meta=meta,
            created_at=self._now(),
        )
