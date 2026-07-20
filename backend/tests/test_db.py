from __future__ import annotations

from app.db.database import Database

_EXPECTED_TABLES = {"runs", "sections", "sources", "events", "settings"}


async def test_init_creates_all_tables():
    db = Database(":memory:")
    await db.init()
    try:
        rows = await db.fetchall("SELECT name FROM sqlite_master WHERE type = 'table'")
        names = {row["name"] for row in rows}
        assert _EXPECTED_TABLES <= names
    finally:
        await db.close()
