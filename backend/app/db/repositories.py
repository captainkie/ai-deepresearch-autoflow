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
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO runs (
              id, query, template, language, require_plan_approval,
              llm_provider, llm_model, search_provider, crawl_provider,
              status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                created_at,
                updated_at,
            ),
        )

    async def get(self, run_id: str) -> aiosqlite.Row | None:
        return await self._db.fetchone("SELECT * FROM runs WHERE id = ?", (run_id,))

    async def list(self) -> list[aiosqlite.Row]:
        return await self._db.fetchall("SELECT * FROM runs ORDER BY created_at DESC, id DESC")

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
