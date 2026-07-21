"""End-to-end (offline, mock) check of the Engine v2 claim pipeline: a full run
emits claim/verification events AND persists them to the new tables.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from httpx import ASGITransport

from app.db.repositories import ClaimRepo, VerificationRepo
from app.main import _shutdown, _startup, create_app
from app.settings import AppSettings

_MOCK = {"llm_provider": "mock", "search_provider": "mock", "crawl_provider": "mock"}


@pytest.fixture
async def app_client():
    """Yields (client, app) so tests can both call the API and read the DB."""
    settings = AppSettings(
        db_path=":memory:",
        cors_origins=["http://localhost:3000"],
        default_require_plan_approval=True,
        rate_limit_enabled=False,
    )
    app = create_app()
    await _startup(app, settings)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post(
            "/api/setup",
            json={"email": "root@example.com", "name": "Root", "password": "supersecret1"},
        )
        client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        yield client, app
    await _shutdown(app)


async def _drain(client, run_id: str, events: list[dict]) -> None:
    async with client.stream("GET", f"/api/runs/{run_id}/stream") as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if line.startswith("data:"):
                payload = line[len("data:") :].strip()
                if payload:
                    events.append(json.loads(payload))


async def test_v2_run_emits_and_persists_claims(app_client):
    client, app = app_client
    resp = await client.post(
        "/api/runs",
        json={"query": "brand X", "config": _MOCK, "require_plan_approval": False},
    )
    run_id = resp.json()["run_id"]

    events: list[dict] = []
    await asyncio.wait_for(_drain(client, run_id, events), timeout=5)

    types = {e["type"] for e in events}
    # The v2 pipeline ran end-to-end.
    assert {"claim", "verification", "note", "report", "done"} <= types
    # claim events carry a grounding quote + source ids.
    claim_events = [e for e in events if e["type"] == "claim"]
    assert claim_events
    assert all(e["data"]["source_ids"] and e["data"]["quote"] for e in claim_events)

    # …and they were persisted to the new tables.
    db = app.state.db
    claims = await ClaimRepo(db).list_by_run(run_id)
    verifs = await VerificationRepo(db).list_by_run(run_id)
    assert len(claims) == len(claim_events)
    assert verifs  # every claim got a verification


async def test_entity_run_projects_comparison_and_confidence_summary(app_client):
    client, app = app_client
    resp = await client.post(
        "/api/runs",
        json={
            "query": "BrandX vs BrandY",
            "template": "competitor_brand",  # entity_mode
            "config": _MOCK,
            "require_plan_approval": False,
        },
    )
    run_id = resp.json()["run_id"]

    events: list[dict] = []
    await asyncio.wait_for(_drain(client, run_id, events), timeout=5)

    # Claims were entity-tagged for the comparison pivot.
    claim_events = [e for e in events if e["type"] == "claim"]
    assert claim_events
    assert any(e["data"].get("entity") for e in claim_events)

    # The report is the entity projection: a cited comparison table.
    report = next(e for e in events if e["type"] == "report")
    assert "## Comparison" in report["data"]["markdown"]

    # confidence_summary rides on both report and done (wire shape).
    summary = report["data"]["confidence_summary"]
    assert set(summary) == {"high", "medium", "low", "contradictions"}
    done = next(e for e in events if e["type"] == "done")
    assert done["data"]["confidence_summary"] == summary


async def test_verification_level_off_reproduces_legacy(app_client):
    client, app = app_client
    await client.post("/api/config", json={"verification_level": "off"})
    resp = await client.post(
        "/api/runs",
        json={"query": "brand X", "config": _MOCK, "require_plan_approval": False},
    )
    run_id = resp.json()["run_id"]

    events: list[dict] = []
    await asyncio.wait_for(_drain(client, run_id, events), timeout=5)

    types = {e["type"] for e in events}
    # Back-compat: no claim/verification events, and nothing persisted.
    assert "claim" not in types
    assert "verification" not in types
    assert {"note", "report", "done"} <= types
    assert await ClaimRepo(app.state.db).list_by_run(run_id) == []
