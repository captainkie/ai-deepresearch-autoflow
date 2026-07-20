"""Async SQLite wrapper around a single ``aiosqlite`` connection.

One :class:`Database` owns one connection for the whole process; aiosqlite
serialises operations onto its own worker thread, so concurrent ``await``s from
the event sink and SSE subscribers are safe. ``init()`` applies ``schema.sql``
(idempotent ``CREATE TABLE IF NOT EXISTS``). Rows come back as ``aiosqlite.Row``
(dict-and-index accessible).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import aiosqlite

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class Database:
    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database.init() must be called before use")
        return self._conn

    async def init(self) -> None:
        if self._conn is not None:
            return
        if self._path not in (":memory:", "") and not self._path.startswith("file:"):
            Path(self._path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")
        schema = _SCHEMA_PATH.read_text(encoding="utf-8")
        await self._conn.executescript(schema)
        await self._conn.commit()

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        await self.connection.execute(sql, params)
        await self.connection.commit()

    async def executemany(self, sql: str, params: Iterable[Sequence[Any]]) -> None:
        await self.connection.executemany(sql, params)
        await self.connection.commit()

    async def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[aiosqlite.Row]:
        cursor = await self.connection.execute(sql, params)
        try:
            return list(await cursor.fetchall())
        finally:
            await cursor.close()

    async def fetchone(self, sql: str, params: Sequence[Any] = ()) -> aiosqlite.Row | None:
        cursor = await self.connection.execute(sql, params)
        try:
            return await cursor.fetchone()
        finally:
            await cursor.close()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
