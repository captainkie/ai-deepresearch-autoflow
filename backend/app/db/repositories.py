"""Async repositories over :class:`Database`.

Thin, parameterised SQL — no HTTP, no engine, no clock. Callers pass timestamps
in (ISO strings) so persistence stays deterministic and testable. JSON columns
are (de)serialised here with the stdlib ``json`` module.

``RunRepo`` owns the run aggregate: the ``runs`` row plus its derived
``sections`` and ``sources`` (all keyed by ``run_id``). ``EventRepo`` owns the
append-only ``events`` log. ``SettingsRepo`` is a JSON key/value store.
"""

from __future__ import annotations

import json
from typing import Any

import aiosqlite

from app.db.database import Database


class RunRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(
        self,
        *,
        id: str,
        query: str,
        template: str,
        language: str,
        require_plan_approval: bool,
        llm_provider: str | None,
        llm_model: str | None,
        search_provider: str | None,
        crawl_provider: str | None,
        status: str,
        created_at: str,
        updated_at: str,
        owner_id: str | None = None,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO runs (
              id, query, template, language, require_plan_approval,
              llm_provider, llm_model, search_provider, crawl_provider,
              status, owner_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id,
                query,
                template,
                language,
                int(require_plan_approval),
                llm_provider,
                llm_model,
                search_provider,
                crawl_provider,
                status,
                owner_id,
                created_at,
                updated_at,
            ),
        )

    async def get(self, run_id: str) -> aiosqlite.Row | None:
        return await self._db.fetchone("SELECT * FROM runs WHERE id = ?", (run_id,))

    async def list(
        self,
        owner_id: str | None = None,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[aiosqlite.Row]:
        sql = "SELECT * FROM runs"
        params: tuple = ()
        if owner_id is not None:
            sql += " WHERE owner_id = ?"
            params = (owner_id,)
        sql += " ORDER BY created_at DESC, id DESC"
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params = (*params, limit, offset)
        return await self._db.fetchall(sql, params)

    async def update_status(
        self, run_id: str, status: str, updated_at: str, error: str | None = None
    ) -> None:
        if error is None:
            await self._db.execute(
                "UPDATE runs SET status = ?, updated_at = ? WHERE id = ?",
                (status, updated_at, run_id),
            )
        else:
            await self._db.execute(
                "UPDATE runs SET status = ?, error = ?, updated_at = ? WHERE id = ?",
                (status, error, updated_at, run_id),
            )

    async def set_report(
        self, run_id: str, report_markdown: str, title: str, updated_at: str
    ) -> None:
        await self._db.execute(
            "UPDATE runs SET report_markdown = ?, title = ?, updated_at = ? WHERE id = ?",
            (report_markdown, title, updated_at, run_id),
        )

    # --- Derived tables (populated by the event sink) -----------------------

    async def upsert_section(
        self,
        run_id: str,
        *,
        id: str,
        idx: int,
        title: str,
        goal: str,
        queries: list[str],
        status: str | None = None,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO sections (run_id, id, idx, title, goal, queries_json, summary, status)
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
            ON CONFLICT (run_id, id) DO UPDATE SET
              idx = excluded.idx, title = excluded.title, goal = excluded.goal,
              queries_json = excluded.queries_json, status = excluded.status
            """,
            (run_id, id, idx, title, goal, json.dumps(queries), status),
        )

    async def set_section_status(self, run_id: str, section_id: str, status: str) -> None:
        await self._db.execute(
            "UPDATE sections SET status = ? WHERE run_id = ? AND id = ?",
            (status, run_id, section_id),
        )

    async def set_section_summary(
        self, run_id: str, section_id: str, summary: str, status: str
    ) -> None:
        await self._db.execute(
            "UPDATE sections SET summary = ?, status = ? WHERE run_id = ? AND id = ?",
            (summary, status, run_id, section_id),
        )

    async def get_sections(self, run_id: str) -> list[aiosqlite.Row]:
        return await self._db.fetchall(
            "SELECT * FROM sections WHERE run_id = ? ORDER BY idx", (run_id,)
        )

    async def delete_sections(self, run_id: str) -> None:
        await self._db.execute("DELETE FROM sections WHERE run_id = ?", (run_id,))

    async def insert_source(
        self,
        run_id: str,
        *,
        ref_num: int,
        title: str,
        url: str,
        snippet: str,
        section_id: str | None,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO sources (run_id, ref_num, section_id, title, url, snippet)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (run_id, ref_num) DO NOTHING
            """,
            (run_id, ref_num, section_id, title, url, snippet),
        )

    async def get_sources(self, run_id: str) -> list[aiosqlite.Row]:
        return await self._db.fetchall(
            "SELECT * FROM sources WHERE run_id = ? ORDER BY ref_num", (run_id,)
        )


class EventRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def append(self, run_id: str, *, seq: int, type_: str, data_json: str, ts: int) -> None:
        await self._db.execute(
            "INSERT INTO events (run_id, seq, type, data_json, ts) VALUES (?, ?, ?, ?, ?)",
            (run_id, seq, type_, data_json, ts),
        )

    async def list_by_run(self, run_id: str) -> list[aiosqlite.Row]:
        return await self._db.fetchall(
            "SELECT * FROM events WHERE run_id = ? ORDER BY seq", (run_id,)
        )

    async def count_by_run(self, run_id: str) -> int:
        row = await self._db.fetchone(
            "SELECT COUNT(*) AS n FROM events WHERE run_id = ?", (run_id,)
        )
        return int(row["n"]) if row is not None else 0


class SettingsRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def get(self, key: str) -> Any:
        row = await self._db.fetchone("SELECT value_json FROM settings WHERE key = ?", (key,))
        return json.loads(row["value_json"]) if row is not None else None

    async def set(self, key: str, value: Any) -> None:
        await self._db.execute(
            """
            INSERT INTO settings (key, value_json) VALUES (?, ?)
            ON CONFLICT (key) DO UPDATE SET value_json = excluded.value_json
            """,
            (key, json.dumps(value)),
        )

    async def all(self) -> dict[str, Any]:
        rows = await self._db.fetchall("SELECT key, value_json FROM settings")
        return {row["key"]: json.loads(row["value_json"]) for row in rows}


class CredentialRepo:
    """Encrypted provider credentials. Stores only ciphertext + nonce + a masked
    hint — never plaintext. Decryption happens in the vault service at call time."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(
        self,
        *,
        id: str,
        provider: str,
        label: str,
        ciphertext: bytes,
        nonce: bytes,
        key_version: int,
        masked_hint: str,
        created_by: str | None,
        created_at: str,
        expires_at: str | None = None,
        status: str = "active",
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO provider_credentials (
              id, provider, label, ciphertext, nonce, key_version, masked_hint,
              status, created_by, created_at, expires_at, last_used_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                id,
                provider,
                label,
                ciphertext,
                nonce,
                key_version,
                masked_hint,
                status,
                created_by,
                created_at,
                expires_at,
            ),
        )

    async def get(self, cred_id: str) -> aiosqlite.Row | None:
        return await self._db.fetchone(
            "SELECT * FROM provider_credentials WHERE id = ?", (cred_id,)
        )

    async def list(self, provider: str | None = None) -> list[aiosqlite.Row]:
        if provider is None:
            return await self._db.fetchall(
                "SELECT * FROM provider_credentials ORDER BY created_at DESC, id DESC"
            )
        return await self._db.fetchall(
            "SELECT * FROM provider_credentials WHERE provider = ? "
            "ORDER BY created_at DESC, id DESC",
            (provider,),
        )

    async def active_for_provider(self, provider: str) -> list[aiosqlite.Row]:
        """Active credentials for a provider, newest first (expiry checked by caller)."""
        return await self._db.fetchall(
            "SELECT * FROM provider_credentials WHERE provider = ? AND status = 'active' "
            "ORDER BY created_at DESC, id DESC",
            (provider,),
        )

    async def all(self) -> list[aiosqlite.Row]:
        return await self._db.fetchall("SELECT * FROM provider_credentials")

    async def set_status(self, cred_id: str, status: str) -> None:
        await self._db.execute(
            "UPDATE provider_credentials SET status = ? WHERE id = ?", (status, cred_id)
        )

    async def set_last_used(self, cred_id: str, last_used_at: str) -> None:
        await self._db.execute(
            "UPDATE provider_credentials SET last_used_at = ? WHERE id = ?",
            (last_used_at, cred_id),
        )

    async def update_ciphertext(
        self, cred_id: str, *, ciphertext: bytes, nonce: bytes, key_version: int
    ) -> None:
        await self._db.execute(
            "UPDATE provider_credentials SET ciphertext = ?, nonce = ?, key_version = ? "
            "WHERE id = ?",
            (ciphertext, nonce, key_version, cred_id),
        )


class AuditRepo:
    """Append-only audit trail of security-relevant actions."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def append(
        self,
        *,
        id: str,
        actor_id: str | None,
        action: str,
        target_type: str | None,
        target_id: str | None,
        meta: dict[str, Any] | None,
        created_at: str,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO audit_log (id, actor_id, action, target_type, target_id, meta_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id,
                actor_id,
                action,
                target_type,
                target_id,
                json.dumps(meta) if meta is not None else None,
                created_at,
            ),
        )

    async def list(self, limit: int = 200) -> list[aiosqlite.Row]:
        return await self._db.fetchall(
            "SELECT * FROM audit_log ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
        )


class UserRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(
        self,
        *,
        id: str,
        email: str,
        name: str,
        password_hash: str | None,
        google_sub: str | None,
        role: str,
        created_at: str,
        disabled: bool = False,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO users (id, email, name, password_hash, google_sub, role, disabled, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (id, email, name, password_hash, google_sub, role, int(disabled), created_at),
        )

    async def get(self, user_id: str) -> aiosqlite.Row | None:
        return await self._db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))

    async def get_by_email(self, email: str) -> aiosqlite.Row | None:
        return await self._db.fetchone("SELECT * FROM users WHERE email = ?", (email,))

    async def get_by_google_sub(self, google_sub: str) -> aiosqlite.Row | None:
        return await self._db.fetchone("SELECT * FROM users WHERE google_sub = ?", (google_sub,))

    async def list(self) -> list[aiosqlite.Row]:
        return await self._db.fetchall("SELECT * FROM users ORDER BY created_at ASC, id ASC")

    async def set_role(self, user_id: str, role: str) -> None:
        await self._db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))

    async def set_disabled(self, user_id: str, disabled: bool) -> None:
        await self._db.execute(
            "UPDATE users SET disabled = ? WHERE id = ?", (int(disabled), user_id)
        )

    async def set_google_sub(self, user_id: str, google_sub: str) -> None:
        await self._db.execute(
            "UPDATE users SET google_sub = ? WHERE id = ?", (google_sub, user_id)
        )

    async def count(self) -> int:
        row = await self._db.fetchone("SELECT COUNT(*) AS n FROM users")
        return int(row["n"]) if row is not None else 0


class RefreshTokenRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(
        self,
        *,
        id: str,
        user_id: str,
        token_hash: str,
        expires_at: str,
        user_agent: str | None,
        created_at: str,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at, revoked_at, user_agent, created_at)
            VALUES (?, ?, ?, ?, NULL, ?, ?)
            """,
            (id, user_id, token_hash, expires_at, user_agent, created_at),
        )

    async def get_by_hash(self, token_hash: str) -> aiosqlite.Row | None:
        return await self._db.fetchone(
            "SELECT * FROM refresh_tokens WHERE token_hash = ?", (token_hash,)
        )

    async def revoke(self, token_id: str, revoked_at: str) -> None:
        await self._db.execute(
            "UPDATE refresh_tokens SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
            (revoked_at, token_id),
        )

    async def revoke_all_for_user(self, user_id: str, revoked_at: str) -> None:
        await self._db.execute(
            "UPDATE refresh_tokens SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
            (revoked_at, user_id),
        )


class ClaimRepo:
    """Claims + their many-to-many link to sources (``claim_sources``)."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(
        self,
        run_id: str,
        *,
        id: str,
        text: str,
        source_ids: list[int],
        quote: str = "",
        section_id: str | None = None,
        entity: str | None = None,
        attribute: str | None = None,
        stance: str | None = None,
        created_at: str,
    ) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO claims "
            "(run_id, id, section_id, text, entity, attribute, quote, stance, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, id, section_id, text, entity, attribute, quote, stance, created_at),
        )
        for ref_num in source_ids:
            await self._db.execute(
                "INSERT OR IGNORE INTO claim_sources (run_id, claim_id, ref_num) VALUES (?, ?, ?)",
                (run_id, id, ref_num),
            )

    async def list_by_run(self, run_id: str) -> list[aiosqlite.Row]:
        return await self._db.fetchall(
            "SELECT * FROM claims WHERE run_id = ? ORDER BY created_at, id", (run_id,)
        )

    async def source_ids(self, run_id: str, claim_id: str) -> list[int]:
        rows = await self._db.fetchall(
            "SELECT ref_num FROM claim_sources WHERE run_id = ? AND claim_id = ? ORDER BY ref_num",
            (run_id, claim_id),
        )
        return [int(r["ref_num"]) for r in rows]


class VerificationRepo:
    """One verification per claim (PK ``run_id, claim_id`` — re-verify upserts)."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def upsert(
        self,
        run_id: str,
        *,
        claim_id: str,
        verdict: str,
        confidence: float | None,
        rationale: str = "",
        verifier_model: str | None = None,
        created_at: str,
    ) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO verifications "
            "(run_id, claim_id, verdict, confidence, rationale, verifier_model, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, claim_id, verdict, confidence, rationale, verifier_model, created_at),
        )

    async def get(self, run_id: str, claim_id: str) -> aiosqlite.Row | None:
        return await self._db.fetchone(
            "SELECT * FROM verifications WHERE run_id = ? AND claim_id = ?", (run_id, claim_id)
        )

    async def list_by_run(self, run_id: str) -> list[aiosqlite.Row]:
        return await self._db.fetchall("SELECT * FROM verifications WHERE run_id = ?", (run_id,))


class ContradictionRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(
        self,
        run_id: str,
        *,
        id: str,
        claim_id_a: str,
        claim_id_b: str,
        entity: str | None = None,
        attribute: str | None = None,
        note: str = "",
    ) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO contradictions "
            "(run_id, id, entity, attribute, claim_id_a, claim_id_b, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, id, entity, attribute, claim_id_a, claim_id_b, note),
        )

    async def list_by_run(self, run_id: str) -> list[aiosqlite.Row]:
        return await self._db.fetchall(
            "SELECT * FROM contradictions WHERE run_id = ? ORDER BY id", (run_id,)
        )
