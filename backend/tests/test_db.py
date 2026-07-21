from __future__ import annotations

import pytest

from app.db.database import Database
from app.db.repositories import (
    ClaimRepo,
    ContradictionRepo,
    EventRepo,
    RunRepo,
    SettingsRepo,
    VerificationRepo,
)

_EXPECTED_TABLES = {
    "runs",
    "sections",
    "sources",
    "events",
    "settings",
    "claims",
    "claim_sources",
    "verifications",
    "contradictions",
}


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.init()
    try:
        yield database
    finally:
        await database.close()


async def test_init_creates_all_tables(db):
    rows = await db.fetchall("SELECT name FROM sqlite_master WHERE type = 'table'")
    names = {row["name"] for row in rows}
    assert _EXPECTED_TABLES <= names


def _new_run(**overrides):
    base = dict(
        id="r1",
        query="Analyze ExampleCo",
        template="deep_research",
        language="en",
        require_plan_approval=False,
        llm_provider="mock",
        llm_model="mock-1",
        search_provider="mock",
        crawl_provider="mock",
        status="queued",
        created_at="2026-07-20T00:00:00+00:00",
        updated_at="2026-07-20T00:00:00+00:00",
    )
    base.update(overrides)
    return base


async def test_run_repo_create_get_list(db):
    repo = RunRepo(db)
    await repo.create(**_new_run(id="r1", created_at="2026-07-20T00:00:01+00:00"))
    await repo.create(
        **_new_run(id="r2", query="Market landscape", created_at="2026-07-20T00:00:02+00:00")
    )

    got = await repo.get("r1")
    assert got is not None
    assert got["query"] == "Analyze ExampleCo"
    assert got["status"] == "queued"

    assert await repo.get("nope") is None

    listed = await repo.list()
    # Newest first (by created_at DESC).
    assert [row["id"] for row in listed] == ["r2", "r1"]


async def test_run_repo_update_status_and_report(db):
    repo = RunRepo(db)
    await repo.create(**_new_run())

    await repo.update_status("r1", "researching", "2026-07-20T00:01:00+00:00")
    row = await repo.get("r1")
    assert row["status"] == "researching"
    assert row["error"] is None

    await repo.update_status("r1", "error", "2026-07-20T00:02:00+00:00", error="boom")
    row = await repo.get("r1")
    assert row["status"] == "error"
    assert row["error"] == "boom"

    await repo.set_report("r1", "# Report\n\n## Sources\n", "Report", "2026-07-20T00:03:00+00:00")
    row = await repo.get("r1")
    assert row["report_markdown"].startswith("# Report")
    assert row["title"] == "Report"


async def test_event_repo_append_and_list_ordered(db):
    RunRepo(db)
    events = EventRepo(db)
    await events.append("r1", seq=2, type_="done", data_json='{"ok":true}', ts=300)
    await events.append("r1", seq=0, type_="status", data_json='{"stage":"planning"}', ts=100)
    await events.append("r1", seq=1, type_="plan", data_json="{}", ts=200)
    await events.append("r2", seq=0, type_="status", data_json="{}", ts=100)

    listed = await events.list_by_run("r1")
    assert [row["seq"] for row in listed] == [0, 1, 2]
    assert [row["type"] for row in listed] == ["status", "plan", "done"]
    assert await events.list_by_run("r2") != []
    assert len(await events.list_by_run("r2")) == 1


async def test_settings_repo_roundtrip_json(db):
    settings = SettingsRepo(db)
    assert await settings.get("missing") is None

    await settings.set("llm_provider", "anthropic")
    await settings.set("require_plan_approval", True)
    await settings.set("nested", {"a": [1, 2, 3]})

    assert await settings.get("llm_provider") == "anthropic"
    assert await settings.get("require_plan_approval") is True
    assert await settings.get("nested") == {"a": [1, 2, 3]}

    # Overwrite existing key.
    await settings.set("llm_provider", "openai")
    assert await settings.get("llm_provider") == "openai"

    everything = await settings.all()
    assert everything["llm_provider"] == "openai"
    assert everything["require_plan_approval"] is True


# --- Engine v2 repos ------------------------------------------------------- #

_TS = "2026-07-21T00:00:00+00:00"


async def test_claim_repo_persists_claim_and_its_sources(db):
    repo = ClaimRepo(db)
    await repo.create(
        "r1",
        id="c1",
        section_id="s1",
        text="BrandX is priced at $9",
        entity="BrandX",
        attribute="pricing",
        quote="priced at $9",
        stance="neutral",
        source_ids=[1, 2],
        created_at=_TS,
    )
    rows = await repo.list_by_run("r1")
    assert len(rows) == 1
    assert rows[0]["entity"] == "BrandX"
    assert rows[0]["section_id"] == "s1"
    # m2m claim ↔ sources
    assert await repo.source_ids("r1", "c1") == [1, 2]
    assert await repo.list_by_run("other") == []


async def test_verification_repo_upsert_is_one_per_claim(db):
    repo = VerificationRepo(db)
    await repo.upsert(
        "r1",
        claim_id="c1",
        verdict="supported",
        confidence=0.9,
        rationale="ok",
        verifier_model="mock-1",
        created_at=_TS,
    )
    row = await repo.get("r1", "c1")
    assert row["verdict"] == "supported"
    # Re-verifying the same claim replaces (PK run_id, claim_id).
    await repo.upsert(
        "r1",
        claim_id="c1",
        verdict="partial",
        confidence=0.4,
        rationale="",
        verifier_model=None,
        created_at=_TS,
    )
    assert (await repo.get("r1", "c1"))["verdict"] == "partial"
    assert len(await repo.list_by_run("r1")) == 1


async def test_contradiction_repo_create_and_list(db):
    repo = ContradictionRepo(db)
    await repo.create(
        "r1",
        id="x1",
        entity="BrandX",
        attribute="pricing",
        claim_id_a="c1",
        claim_id_b="c2",
        note="$9 vs $12",
    )
    rows = await repo.list_by_run("r1")
    assert len(rows) == 1
    assert {rows[0]["claim_id_a"], rows[0]["claim_id_b"]} == {"c1", "c2"}
    assert rows[0]["attribute"] == "pricing"
