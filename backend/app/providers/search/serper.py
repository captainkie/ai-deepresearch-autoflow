"""Serper (google.serper.dev) search adapter."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from app.models.schemas import SearchResult

GetKey = Callable[[str], str | None]


class SerperSearchProvider:
    URL = "https://google.serper.dev/search"

    def __init__(self, client: httpx.AsyncClient, get_key: GetKey) -> None:
        self._client = client
        self._get_key = get_key

    async def search(self, query: str, k: int = 6) -> list[SearchResult]:
        response = await self._client.post(
            self.URL,
            headers={"X-API-KEY": self._get_key("serper") or ""},
            json={"q": query, "num": k},
        )
        response.raise_for_status()
        data = response.json()
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("link", ""),
                snippet=r.get("snippet", ""),
            )
            for r in data.get("organic", [])
        ]
