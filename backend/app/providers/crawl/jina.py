"""Jina reader crawl adapter (r.jina.ai → clean markdown)."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from app.models.schemas import PageContent

GetKey = Callable[[str], str | None]


class JinaCrawlProvider:
    BASE = "https://r.jina.ai/"

    def __init__(self, client: httpx.AsyncClient, get_key: GetKey | None = None) -> None:
        self._client = client
        self._get_key = get_key

    async def fetch(self, url: str) -> PageContent:
        headers = {}
        key = self._get_key("jina") if self._get_key else None
        if key:
            headers["Authorization"] = f"Bearer {key}"
        try:
            response = await self._client.get(self.BASE + url, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return PageContent(url=url, ok=False, error=str(exc))
        return PageContent(url=url, text=response.text, ok=True)
