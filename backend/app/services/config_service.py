"""Runtime provider configuration + availability.

``available_*`` report which providers are usable right now: the keyless mocks
(and DuckDuckGo/Jina/Trafilatura) are always listed; keyed providers appear only
when :func:`provider_keys.get_key` finds a credential. ``current``/``update``
read and write the selected provider config to the ``settings`` table. The
returned shape matches ``ConfigResponse`` in ``docs/API_CONTRACT.md``.
"""

from __future__ import annotations

import importlib.util
from typing import Any

from app.db.database import Database
from app.db.repositories import SettingsRepo
from app.services.provider_keys import get_key
from app.settings import AppSettings

_DEFAULT_LLM_PROVIDER = "mock"
_DEFAULT_LLM_MODEL = "mock-1"
_DEFAULT_SEARCH_PROVIDER = "mock"

_KEYED_LLM = ("anthropic", "openai", "gemini")
_KEYED_SEARCH = ("tavily", "serper", "exa")

# Which settings keys ``update`` is allowed to write.
_WRITABLE = ("llm_provider", "llm_model", "search_provider", "require_plan_approval")


def _trafilatura_available() -> bool:
    return importlib.util.find_spec("trafilatura") is not None


class ConfigService:
    def __init__(self, db: Database, app_settings: AppSettings) -> None:
        self._settings = SettingsRepo(db)
        self._app = app_settings

    def available_llm(self) -> list[str]:
        return ["mock", *[p for p in _KEYED_LLM if get_key(p)]]

    def available_search(self) -> list[str]:
        return ["mock", "duckduckgo", *[p for p in _KEYED_SEARCH if get_key(p)]]

    def available_crawl(self) -> list[str]:
        out = ["mock", "jina"]
        if _trafilatura_available():
            out.append("trafilatura")
        return out

    async def current(self) -> dict[str, Any]:
        stored = await self._settings.all()
        require = stored.get("require_plan_approval")
        if require is None:
            require = self._app.default_require_plan_approval
        return {
            "llm": {
                "provider": stored.get("llm_provider", _DEFAULT_LLM_PROVIDER),
                "model": stored.get("llm_model", _DEFAULT_LLM_MODEL),
                "available": self.available_llm(),
            },
            "search": {
                "provider": stored.get("search_provider", _DEFAULT_SEARCH_PROVIDER),
                "available": self.available_search(),
            },
            "require_plan_approval": bool(require),
        }

    async def update(self, patch: dict[str, Any]) -> dict[str, Any]:
        for key in _WRITABLE:
            if patch.get(key) is not None:
                await self._settings.set(key, patch[key])
        return await self.current()
