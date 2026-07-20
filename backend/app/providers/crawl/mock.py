"""Deterministic mock crawl provider (offline, no network, no randomness)."""

from __future__ import annotations

from app.models.schemas import PageContent


class MockCrawlProvider:
    """Returns a deterministic paragraph that embeds the requested url."""

    async def fetch(self, url: str) -> PageContent:
        text = (
            f"Content fetched from {url}. "
            "This deterministic page discusses the topic in detail. "
            "It covers background, notable facts, and analysis relevant to the "
            "section goal, with concrete points a researcher can summarize. "
            f"Canonical source URL: {url}."
        )
        return PageContent(url=url, title=f"Page at {url}", text=text, ok=True)
