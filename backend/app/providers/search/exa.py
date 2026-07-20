"""Exa (api.exa.ai) search adapter."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from app.models.schemas import SearchResult

GetKey = Callable[[str], str | None]


class ExaSearchProvider:
    URL = "https://api.exa.ai/search"

    def __init__(self, client: httpx.AsyncClient, get_key: GetKey) -> None:
        self._client = client
        self._get_key = get_key

    async def search(self, query: str, k: int = 6) -> list[SearchResult]:
        response = await self._client.post(
            self.URL,
            headers={"x-api-key": self._get_key("exa") or ""},
            json={"query": query, "numResults": k},
        )
        response.raise_for_status()
        data = response.json()
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("text") or r.get("snippet", ""),
                score=r.get("score"),
            )
            for r in data.get("results", [])
        ]
