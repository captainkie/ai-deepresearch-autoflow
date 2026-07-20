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
