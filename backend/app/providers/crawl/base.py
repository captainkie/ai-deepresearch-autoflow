"""Crawl provider interface."""

from __future__ import annotations

from typing import Protocol

from app.models.schemas import PageContent


class CrawlProvider(Protocol):
    async def fetch(self, url: str) -> PageContent: ...
