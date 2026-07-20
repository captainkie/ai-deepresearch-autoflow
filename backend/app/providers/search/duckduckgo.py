"""DuckDuckGo search adapter (keyless, via the ``ddgs`` package)."""

from __future__ import annotations

import asyncio

from ddgs import DDGS

from app.models.schemas import SearchResult


class DuckDuckGoSearchProvider:
    async def search(self, query: str, k: int = 6) -> list[SearchResult]:
        rows = await asyncio.to_thread(self._search_sync, query, k)
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("href") or r.get("url", ""),
                snippet=r.get("body") or r.get("snippet", ""),
            )
            for r in rows
        ]

    @staticmethod
    def _search_sync(query: str, k: int) -> list[dict]:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=k))
