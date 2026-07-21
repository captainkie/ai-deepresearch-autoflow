from __future__ import annotations

import pytest

from app.db.database import Database
from app.services.config_service import ConfigService
from app.settings import AppSettings


@pytest.fixture
async def config_service():
    db = Database(":memory:")
    await db.init()
    try:
        yield ConfigService(db, AppSettings())
    finally:
        await db.close()


def test_available_llm_always_includes_mock(config_service, monkeypatch):
    for env in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    available = config_service.available_llm()
    assert available == ["mock"]


def test_available_llm_adds_keyed_provider(config_service, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    available = config_service.available_llm()
    assert "mock" in available
    assert "anthropic" in available


def test_available_search_includes_mock_and_duckduckgo(config_service, monkeypatch):
    for env in ("TAVILY_API_KEY", "SERPER_API_KEY", "EXA_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    available = config_service.available_search()
    assert "mock" in available
    assert "duckduckgo" in available
    assert "tavily" not in available


async def test_current_and_update_roundtrip(config_service):
    current = await config_service.current()
    assert current["llm"]["provider"] == "mock"
    assert "mock" in current["llm"]["available"]

    updated = await config_service.update(
        {"llm_provider": "anthropic", "require_plan_approval": False}
    )
    assert updated["llm"]["provider"] == "anthropic"
    assert updated["require_plan_approval"] is False


async def test_templates_endpoint(client):
    resp = await client.get("/api/templates")
    assert resp.status_code == 200
    templates = resp.json()["templates"]
    assert len(templates) >= 3
    ids = {t["id"] for t in templates}
    assert "deep_research" in ids
    for t in templates:
        assert {"id", "name", "description", "audience"} <= t.keys()


async def test_get_config_endpoint(auth_client):
    resp = await auth_client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert "mock" in body["llm"]["available"]
    assert "mock" in body["search"]["available"]
    assert "require_plan_approval" in body


async def test_get_config_requires_auth(client):
    # Config reveals which providers are wired up — gate it behind a session.
    resp = await client.get("/api/config")
    assert resp.status_code == 401


async def test_post_config_persists(auth_client):
    resp = await auth_client.post("/api/config", json={"search_provider": "duckduckgo"})
    assert resp.status_code == 200
    assert resp.json()["search"]["provider"] == "duckduckgo"

    # Persisted across requests (same in-memory DB / app.state).
    resp2 = await auth_client.get("/api/config")
    assert resp2.json()["search"]["provider"] == "duckduckgo"
