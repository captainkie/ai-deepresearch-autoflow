"""trafilatura crawl adapter (optional ``crawl`` extra)."""

from __future__ import annotations

import httpx

from app.models.schemas import PageContent


class TrafilaturaCrawlProvider:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def fetch(self, url: str) -> PageContent:
        try:
            import trafilatura
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "trafilatura is not installed; install the extra with "
                "`uv sync --extra crawl`"
            ) from exc
        try:
            response = await self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return PageContent(url=url, ok=False, error=str(exc))
        text = trafilatura.extract(response.text) or ""
        return PageContent(url=url, text=text, ok=bool(text))
